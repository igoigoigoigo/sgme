"""Conexão e esquema do SQLite.

Única classe do sistema que sabe abrir conexões. Na Entrega 1, cada função
chamava `sqlite3.connect` e `conn.close()` manualmente (e algumas esqueciam de
fechar em caso de erro). Aqui o gerenciador de contexto garante commit,
rollback e fechamento.

O esquema é compatível com o `manutencao.db` da Entrega 1: as tabelas são as
mesmas e as colunas novas são adicionadas por migração (`ALTER TABLE`).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    perfil TEXT NOT NULL,
    status TEXT DEFAULT 'Disponível'
);
CREATE TABLE IF NOT EXISTS equipamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT,
    ativo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ordens_servico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipamento_id INTEGER,
    criador_id INTEGER,
    tecnico_id INTEGER,
    falha_apontada TEXT,
    criticidade TEXT,
    status TEXT DEFAULT 'Aberta',
    diagnostico TEXT,
    horas_trabalhadas REAL DEFAULT 0.0,
    pecas_utilizadas TEXT,
    parecer_gestor TEXT,
    FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id),
    FOREIGN KEY(criador_id) REFERENCES usuarios(id),
    FOREIGN KEY(tecnico_id) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS usuario_especialidades (
    usuario_id INTEGER NOT NULL,
    especialidade TEXT NOT NULL,
    PRIMARY KEY (usuario_id, especialidade),
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS os_especialidades (
    os_id INTEGER NOT NULL,
    especialidade TEXT NOT NULL,
    PRIMARY KEY (os_id, especialidade),
    FOREIGN KEY(os_id) REFERENCES ordens_servico(id)
);
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    os_id INTEGER,
    descricao TEXT,
    data_hora TEXT,
    FOREIGN KEY(os_id) REFERENCES ordens_servico(id)
);
"""

# (tabela, coluna, definição) — colunas novas da Entrega 2
_MIGRACOES = [
    ("ordens_servico", "data_abertura", "TEXT"),
    ("ordens_servico", "data_encerramento", "TEXT"),
]

_INDICES = """
CREATE INDEX IF NOT EXISTS idx_os_status ON ordens_servico(status);
CREATE INDEX IF NOT EXISTS idx_os_tecnico ON ordens_servico(tecnico_id);
CREATE INDEX IF NOT EXISTS idx_historico_os ON historico(os_id);
CREATE INDEX IF NOT EXISTS idx_os_especialidade ON os_especialidades(especialidade);
"""


class Database:
    def __init__(self, caminho: str) -> None:
        self.caminho = caminho

    @contextmanager
    def conexao(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.caminho)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def inicializar(self) -> None:
        with self.conexao() as conn:
            conn.executescript(_ESQUEMA)
            for tabela, coluna, definicao in _MIGRACOES:
                existentes = {r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")}
                if coluna not in existentes:
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
            conn.executescript(_INDICES)
            self._normalizar_legado(conn)

    @staticmethod
    def _normalizar_legado(conn: sqlite3.Connection) -> None:
        """A Entrega 1 aceitava criticidade digitada livremente ('Media', 'alta'...)."""
        for valor in ("Baixa", "Média", "Alta"):
            semacento = valor.replace("é", "e")
            conn.execute(
                "UPDATE ordens_servico SET criticidade = ? "
                "WHERE lower(criticidade) IN (lower(?), lower(?)) AND criticidade <> ?",
                (valor, valor, semacento, valor),
            )
        conn.execute(
            "UPDATE ordens_servico SET criticidade = 'Média' "
            "WHERE criticidade IS NULL OR criticidade NOT IN ('Baixa', 'Média', 'Alta')"
        )
        conn.execute(
            "UPDATE ordens_servico SET falha_apontada = '(não informada)' "
            "WHERE falha_apontada IS NULL OR trim(falha_apontada) = ''"
        )
        # OS legadas sem data de abertura herdam a data do primeiro evento do histórico
        conn.execute(
            """UPDATE ordens_servico SET data_abertura = (
                   SELECT MIN(h.data_hora) FROM historico h WHERE h.os_id = ordens_servico.id)
               WHERE data_abertura IS NULL"""
        )

    def esta_vazio(self) -> bool:
        with self.conexao() as conn:
            return conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
