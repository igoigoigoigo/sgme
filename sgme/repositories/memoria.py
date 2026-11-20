"""Repositórios em memória.

Usados nos testes automatizados e no modo de demonstração sem disco
(`SGME_STORAGE=memoria`). Por respeitarem exatamente os mesmos contratos das
versões SQLite, podem substituí-las sem que os serviços percebam
(Princípio de Substituição de Liskov).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from sgme.domain.entidades import (
    Equipamento, EventoHistorico, FiltroOS, OrdemServico, Perfil, Usuario,
)
from .filtros import atende_filtro
from .interfaces import (
    EquipamentoRepository, HistoricoRepository, OrdemServicoRepository, UsuarioRepository,
)


class _Tabela:
    """Armazena cópias para imitar um banco real (alterar o objeto retornado
    não altera o dado persistido até que `atualizar` seja chamado)."""

    def __init__(self) -> None:
        self._dados: dict[int, object] = {}
        self._proximo_id = 1

    def inserir(self, obj):
        obj.id = self._proximo_id
        self._proximo_id += 1
        self._dados[obj.id] = deepcopy(obj)
        return obj

    def obter(self, obj_id):
        obj = self._dados.get(obj_id)
        return deepcopy(obj) if obj else None

    def gravar(self, obj) -> None:
        if obj.id not in self._dados:
            raise KeyError(obj.id)
        self._dados[obj.id] = deepcopy(obj)

    def todos(self) -> list:
        return [deepcopy(o) for o in self._dados.values()]


class UsuarioRepositoryMemoria(UsuarioRepository):
    def __init__(self) -> None:
        self._t = _Tabela()

    def obter(self, usuario_id: int) -> Usuario | None:
        return self._t.obter(usuario_id)

    def listar(self, perfil: Perfil | None = None) -> list[Usuario]:
        return [u for u in self._t.todos() if perfil is None or u.perfil is perfil]

    def adicionar(self, usuario: Usuario) -> Usuario:
        return self._t.inserir(usuario)

    def atualizar(self, usuario: Usuario) -> None:
        self._t.gravar(usuario)


class EquipamentoRepositoryMemoria(EquipamentoRepository):
    def __init__(self) -> None:
        self._t = _Tabela()

    def obter(self, equipamento_id: int) -> Equipamento | None:
        return self._t.obter(equipamento_id)

    def listar(self, apenas_ativos: bool = False) -> list[Equipamento]:
        return [e for e in self._t.todos() if e.ativo or not apenas_ativos]

    def adicionar(self, equipamento: Equipamento) -> Equipamento:
        return self._t.inserir(equipamento)

    def atualizar(self, equipamento: Equipamento) -> None:
        self._t.gravar(equipamento)


class OrdemServicoRepositoryMemoria(OrdemServicoRepository):
    def __init__(self) -> None:
        self._t = _Tabela()

    def obter(self, os_id: int) -> OrdemServico | None:
        return self._t.obter(os_id)

    def listar(self, filtro: FiltroOS | None = None) -> list[OrdemServico]:
        ordens = [o for o in self._t.todos() if atende_filtro(o, filtro)]
        return sorted(ordens, key=lambda o: o.id, reverse=True)

    def adicionar(self, ordem: OrdemServico) -> OrdemServico:
        return self._t.inserir(ordem)

    def atualizar(self, ordem: OrdemServico) -> None:
        self._t.gravar(ordem)


class HistoricoRepositoryMemoria(HistoricoRepository):
    def __init__(self) -> None:
        self._eventos: list[EventoHistorico] = []

    def adicionar(self, evento: EventoHistorico) -> EventoHistorico:
        salvo = replace(evento, id=len(self._eventos) + 1)
        self._eventos.append(salvo)
        return salvo

    def listar_por_os(self, os_id: int) -> list[EventoHistorico]:
        return [e for e in self._eventos if e.os_id == os_id]

    def listar_recentes(self, limite: int = 10) -> list[EventoHistorico]:
        return list(reversed(self._eventos))[:limite]
