"""Implementações SQLite dos repositórios.

Todo SQL do sistema está concentrado aqui. Cada classe converte linhas do
banco em entidades do domínio (e vice-versa) — o resto da aplicação nunca vê
uma tupla ou um `sqlite3.Row`.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from sgme.domain.entidades import (
    FORMATO_DATA, Equipamento, EventoHistorico, FiltroOS, OrdemServico, Perfil, Usuario,
)
from sgme.domain.status_os import StatusOS
from sgme.repositories.interfaces import (
    EquipamentoRepository, HistoricoRepository, OrdemServicoRepository, UsuarioRepository,
)
from .database import Database


def _data(texto: str | None) -> datetime | None:
    return datetime.strptime(texto, FORMATO_DATA) if texto else None


def _texto(data: datetime | None) -> str | None:
    return data.strftime(FORMATO_DATA) if data else None


class _RepositorioSQLite:
    def __init__(self, db: Database) -> None:
        self._db = db


class UsuarioRepositorySQLite(_RepositorioSQLite, UsuarioRepository):
    @staticmethod
    def _mapear(r: sqlite3.Row) -> Usuario:
        return Usuario(id=r["id"], nome=r["nome"], perfil=r["perfil"], status=r["status"])

    def obter(self, usuario_id: int) -> Usuario | None:
        with self._db.conexao() as c:
            r = c.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        return self._mapear(r) if r else None

    def listar(self, perfil: Perfil | None = None) -> list[Usuario]:
        sql, params = "SELECT * FROM usuarios", ()
        if perfil is not None:
            sql, params = sql + " WHERE perfil = ?", (perfil.value,)
        with self._db.conexao() as c:
            return [self._mapear(r) for r in c.execute(sql + " ORDER BY nome", params)]

    def adicionar(self, usuario: Usuario) -> Usuario:
        with self._db.conexao() as c:
            cur = c.execute(
                "INSERT INTO usuarios (nome, perfil, status) VALUES (?, ?, ?)",
                (usuario.nome, usuario.perfil.value, usuario.status.value),
            )
            usuario.id = cur.lastrowid
        return usuario

    def atualizar(self, usuario: Usuario) -> None:
        with self._db.conexao() as c:
            c.execute(
                "UPDATE usuarios SET nome = ?, perfil = ?, status = ? WHERE id = ?",
                (usuario.nome, usuario.perfil.value, usuario.status.value, usuario.id),
            )


class EquipamentoRepositorySQLite(_RepositorioSQLite, EquipamentoRepository):
    @staticmethod
    def _mapear(r: sqlite3.Row) -> Equipamento:
        return Equipamento(id=r["id"], nome=r["nome"], descricao=r["descricao"] or "",
                           ativo=bool(r["ativo"]))

    def obter(self, equipamento_id: int) -> Equipamento | None:
        with self._db.conexao() as c:
            r = c.execute("SELECT * FROM equipamentos WHERE id = ?", (equipamento_id,)).fetchone()
        return self._mapear(r) if r else None

    def listar(self, apenas_ativos: bool = False) -> list[Equipamento]:
        sql = "SELECT * FROM equipamentos"
        if apenas_ativos:
            sql += " WHERE ativo = 1"
        with self._db.conexao() as c:
            return [self._mapear(r) for r in c.execute(sql + " ORDER BY nome")]

    def adicionar(self, equipamento: Equipamento) -> Equipamento:
        with self._db.conexao() as c:
            cur = c.execute(
                "INSERT INTO equipamentos (nome, descricao, ativo) VALUES (?, ?, ?)",
                (equipamento.nome, equipamento.descricao, int(equipamento.ativo)),
            )
            equipamento.id = cur.lastrowid
        return equipamento

    def atualizar(self, equipamento: Equipamento) -> None:
        with self._db.conexao() as c:
            c.execute(
                "UPDATE equipamentos SET nome = ?, descricao = ?, ativo = ? WHERE id = ?",
                (equipamento.nome, equipamento.descricao, int(equipamento.ativo), equipamento.id),
            )


class OrdemServicoRepositorySQLite(_RepositorioSQLite, OrdemServicoRepository):
    _COLUNAS = (
        "equipamento_id", "criador_id", "tecnico_id", "falha_apontada", "criticidade",
        "status", "diagnostico", "horas_trabalhadas", "pecas_utilizadas", "parecer_gestor",
        "data_abertura", "data_encerramento",
    )

    @staticmethod
    def _mapear(r: sqlite3.Row) -> OrdemServico:
        return OrdemServico(
            id=r["id"], equipamento_id=r["equipamento_id"], criador_id=r["criador_id"],
            tecnico_id=r["tecnico_id"], falha_apontada=r["falha_apontada"],
            criticidade=r["criticidade"], status=r["status"], diagnostico=r["diagnostico"],
            horas_trabalhadas=r["horas_trabalhadas"], pecas_utilizadas=r["pecas_utilizadas"],
            parecer_gestor=r["parecer_gestor"], data_abertura=_data(r["data_abertura"]),
            data_encerramento=_data(r["data_encerramento"]),
        )

    def _valores(self, o: OrdemServico) -> tuple:
        return (
            o.equipamento_id, o.criador_id, o.tecnico_id, o.falha_apontada, o.criticidade.value,
            o.status.value, o.diagnostico, o.horas_trabalhadas, o.pecas_utilizadas,
            o.parecer_gestor, _texto(o.data_abertura), _texto(o.data_encerramento),
        )

    def obter(self, os_id: int) -> OrdemServico | None:
        with self._db.conexao() as c:
            r = c.execute("SELECT * FROM ordens_servico WHERE id = ?", (os_id,)).fetchone()
        return self._mapear(r) if r else None

    def listar(self, filtro: FiltroOS | None = None) -> list[OrdemServico]:
        condicoes: list[str] = []
        params: list = []
        if filtro:
            if filtro.status is not None:
                condicoes.append("status = ?"); params.append(filtro.status.value)
            if filtro.criticidade is not None:
                condicoes.append("criticidade = ?"); params.append(filtro.criticidade.value)
            if filtro.tecnico_id is not None:
                condicoes.append("tecnico_id = ?"); params.append(filtro.tecnico_id)
            if filtro.equipamento_id is not None:
                condicoes.append("equipamento_id = ?"); params.append(filtro.equipamento_id)
            if filtro.apenas_ativas:
                finais = (StatusOS.CONCLUIDA.value, StatusOS.CANCELADA.value)
                condicoes.append("status NOT IN (?, ?)"); params.extend(finais)
            if filtro.texto:
                condicoes.append(
                    "(CAST(id AS TEXT) LIKE ? OR falha_apontada LIKE ? OR diagnostico LIKE ?)"
                )
                termo = f"%{filtro.texto.strip()}%"
                params.extend([termo, termo, termo])
        sql = "SELECT * FROM ordens_servico"
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        with self._db.conexao() as c:
            return [self._mapear(r) for r in c.execute(sql + " ORDER BY id DESC", params)]

    def adicionar(self, ordem: OrdemServico) -> OrdemServico:
        marcadores = ", ".join("?" * len(self._COLUNAS))
        with self._db.conexao() as c:
            cur = c.execute(
                f"INSERT INTO ordens_servico ({', '.join(self._COLUNAS)}) VALUES ({marcadores})",
                self._valores(ordem),
            )
            ordem.id = cur.lastrowid
        return ordem

    def atualizar(self, ordem: OrdemServico) -> None:
        atribuicoes = ", ".join(f"{col} = ?" for col in self._COLUNAS)
        with self._db.conexao() as c:
            c.execute(f"UPDATE ordens_servico SET {atribuicoes} WHERE id = ?",
                      (*self._valores(ordem), ordem.id))


class HistoricoRepositorySQLite(_RepositorioSQLite, HistoricoRepository):
    @staticmethod
    def _mapear(r: sqlite3.Row) -> EventoHistorico:
        return EventoHistorico(id=r["id"], os_id=r["os_id"], descricao=r["descricao"],
                               data_hora=_data(r["data_hora"]))

    def adicionar(self, evento: EventoHistorico) -> EventoHistorico:
        with self._db.conexao() as c:
            cur = c.execute(
                "INSERT INTO historico (os_id, descricao, data_hora) VALUES (?, ?, ?)",
                (evento.os_id, evento.descricao, _texto(evento.data_hora)),
            )
            novo_id = cur.lastrowid
        return EventoHistorico(evento.os_id, evento.descricao, evento.data_hora, novo_id)

    def listar_por_os(self, os_id: int) -> list[EventoHistorico]:
        with self._db.conexao() as c:
            linhas = c.execute(
                "SELECT * FROM historico WHERE os_id = ? ORDER BY id ASC", (os_id,)
            ).fetchall()
        return [self._mapear(r) for r in linhas]

    def listar_recentes(self, limite: int = 10) -> list[EventoHistorico]:
        with self._db.conexao() as c:
            linhas = c.execute(
                "SELECT * FROM historico ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
        return [self._mapear(r) for r in linhas]
