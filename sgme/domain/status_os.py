"""Ciclo de vida da Ordem de Serviço — padrão State.

Na Entrega 1 o status era uma string livre: qualquer função podia gravar
qualquer valor (ex.: encerrar uma OS que nem tinha sido atribuída, ou o técnico
mudar o status de uma OS já concluída). Aqui cada status é um objeto que sabe
para quais estados pode transitar e quais operações aceita.

Adicionar um novo status = criar uma nova subclasse e registrá-la (Aberto/Fechado).
"""
from __future__ import annotations

from abc import ABC
from enum import Enum


class StatusOS(str, Enum):
    ABERTA = "Aberta"
    EM_ANDAMENTO = "Em Andamento"
    EM_EXECUCAO = "Em Execução"
    AGUARDANDO_PECA = "Aguardando Peça"
    REPARO_FINALIZADO = "Reparo Finalizado"
    CONCLUIDA = "Concluída"
    CANCELADA = "Cancelada"

    def __str__(self) -> str:  # facilita uso em templates
        return self.value


class EstadoOS(ABC):
    """Estado abstrato. Subclasses declaram suas regras via atributos de classe."""

    status: StatusOS
    transicoes: frozenset[StatusOS] = frozenset()
    aceita_trabalho_tecnico: bool = False   # diagnóstico / apontamento
    aceita_atribuicao: bool = False          # gestor pode (re)atribuir técnico
    final: bool = False

    def pode_ir_para(self, destino: StatusOS) -> bool:
        return destino in self.transicoes

    @property
    def ativo(self) -> bool:
        """OS ativa ocupa o técnico."""
        return not self.final and self.status is not StatusOS.ABERTA


class Aberta(EstadoOS):
    status = StatusOS.ABERTA
    transicoes = frozenset({StatusOS.EM_ANDAMENTO, StatusOS.CANCELADA})
    aceita_atribuicao = True


class EmAndamento(EstadoOS):
    status = StatusOS.EM_ANDAMENTO
    transicoes = frozenset({
        StatusOS.EM_EXECUCAO, StatusOS.AGUARDANDO_PECA,
        StatusOS.REPARO_FINALIZADO, StatusOS.CANCELADA,
    })
    aceita_trabalho_tecnico = True
    aceita_atribuicao = True


class EmExecucao(EstadoOS):
    status = StatusOS.EM_EXECUCAO
    transicoes = frozenset({
        StatusOS.AGUARDANDO_PECA, StatusOS.REPARO_FINALIZADO, StatusOS.CANCELADA,
    })
    aceita_trabalho_tecnico = True
    aceita_atribuicao = True


class AguardandoPeca(EstadoOS):
    status = StatusOS.AGUARDANDO_PECA
    transicoes = frozenset({
        StatusOS.EM_EXECUCAO, StatusOS.REPARO_FINALIZADO, StatusOS.CANCELADA,
    })
    aceita_trabalho_tecnico = True
    aceita_atribuicao = True


class ReparoFinalizado(EstadoOS):
    status = StatusOS.REPARO_FINALIZADO
    # O gestor aprova (Concluída), cancela, ou devolve para execução.
    transicoes = frozenset({
        StatusOS.CONCLUIDA, StatusOS.EM_EXECUCAO, StatusOS.CANCELADA,
    })


class Concluida(EstadoOS):
    status = StatusOS.CONCLUIDA
    final = True


class Cancelada(EstadoOS):
    status = StatusOS.CANCELADA
    final = True


_ESTADOS: dict[StatusOS, EstadoOS] = {
    e.status: e() for e in (
        Aberta, EmAndamento, EmExecucao, AguardandoPeca,
        ReparoFinalizado, Concluida, Cancelada,
    )
}

# Status que o técnico pode escolher manualmente (equivalente ao menu da Entrega 1)
STATUS_OPERACIONAIS_TECNICO: tuple[StatusOS, ...] = (
    StatusOS.EM_EXECUCAO, StatusOS.AGUARDANDO_PECA, StatusOS.REPARO_FINALIZADO,
)


def estado_de(status: StatusOS | str) -> EstadoOS:
    """Retorna o objeto-estado para um status (aceita o texto gravado no banco)."""
    try:
        return _ESTADOS[StatusOS(status)]
    except ValueError as exc:
        raise ValueError(f"Status desconhecido: {status!r}") from exc


def status_ativos() -> tuple[StatusOS, ...]:
    return tuple(s for s, e in _ESTADOS.items() if e.ativo)
