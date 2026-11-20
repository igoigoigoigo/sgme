"""Contratos de persistência — padrão Repository + Inversão de Dependência.

Os serviços conhecem apenas estas abstrações. Trocar SQLite por PostgreSQL,
arquivos JSON ou memória não exige mudar uma linha da regra de negócio.

Segregação de Interfaces: cada agregado tem seu repositório pequeno e
específico, em vez de uma única classe "Banco" com dezenas de métodos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from sgme.domain.entidades import (
    Equipamento, EventoHistorico, FiltroOS, OrdemServico, Perfil, Usuario,
)


class UsuarioRepository(ABC):
    @abstractmethod
    def obter(self, usuario_id: int) -> Usuario | None: ...

    @abstractmethod
    def listar(self, perfil: Perfil | None = None) -> list[Usuario]: ...

    @abstractmethod
    def adicionar(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    def atualizar(self, usuario: Usuario) -> None: ...


class EquipamentoRepository(ABC):
    @abstractmethod
    def obter(self, equipamento_id: int) -> Equipamento | None: ...

    @abstractmethod
    def listar(self, apenas_ativos: bool = False) -> list[Equipamento]: ...

    @abstractmethod
    def adicionar(self, equipamento: Equipamento) -> Equipamento: ...

    @abstractmethod
    def atualizar(self, equipamento: Equipamento) -> None: ...


class OrdemServicoRepository(ABC):
    @abstractmethod
    def obter(self, os_id: int) -> OrdemServico | None: ...

    @abstractmethod
    def listar(self, filtro: FiltroOS | None = None) -> list[OrdemServico]: ...

    @abstractmethod
    def adicionar(self, ordem: OrdemServico) -> OrdemServico: ...

    @abstractmethod
    def atualizar(self, ordem: OrdemServico) -> None: ...


class HistoricoRepository(ABC):
    @abstractmethod
    def adicionar(self, evento: EventoHistorico) -> EventoHistorico: ...

    @abstractmethod
    def listar_por_os(self, os_id: int) -> list[EventoHistorico]: ...

    @abstractmethod
    def listar_recentes(self, limite: int = 10) -> list[EventoHistorico]: ...
