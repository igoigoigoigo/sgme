"""Eventos de OS — padrão Observer.

Na Entrega 1, cada função precisava lembrar de chamar `registrar_historico` e
de atualizar o status do técnico (e `encerramento_administrativo` liberava o
técnico mesmo que ele ainda tivesse outras OS em andamento).

Agora o serviço apenas *publica* o que aconteceu. Observadores independentes
reagem: um grava o histórico, outro recalcula a disponibilidade dos técnicos.
Novas reações (ex.: enviar e-mail, log de auditoria) entram como novos
observadores, sem tocar no serviço (Aberto/Fechado).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sgme.domain.entidades import EventoHistorico, FiltroOS, StatusTecnico
from sgme.repositories.interfaces import (
    HistoricoRepository, OrdemServicoRepository, UsuarioRepository,
)


class TipoEvento(str, Enum):
    ABERTA = "aberta"
    ATRIBUIDA = "atribuida"
    DIAGNOSTICO = "diagnostico"
    APONTAMENTO = "apontamento"
    STATUS_ALTERADO = "status_alterado"
    DEVOLVIDA = "devolvida"
    ENCERRADA = "encerrada"


@dataclass(frozen=True)
class EventoOS:
    tipo: TipoEvento
    os_id: int
    descricao: str
    ocorrido_em: datetime
    tecnicos_afetados: tuple[int, ...] = field(default_factory=tuple)


class ObservadorOS(ABC):
    @abstractmethod
    def notificar(self, evento: EventoOS) -> None: ...


class PublicadorEventos:
    """Sujeito do Observer: mantém a lista de inscritos e os notifica."""

    def __init__(self) -> None:
        self._observadores: list[ObservadorOS] = []

    def inscrever(self, observador: ObservadorOS) -> None:
        self._observadores.append(observador)

    def publicar(self, evento: EventoOS) -> None:
        for observador in self._observadores:
            observador.notificar(evento)


class RegistroHistoricoObserver(ObservadorOS):
    """Grava toda movimentação da OS na tabela de histórico."""

    def __init__(self, historico: HistoricoRepository) -> None:
        self._historico = historico

    def notificar(self, evento: EventoOS) -> None:
        self._historico.adicionar(
            EventoHistorico(evento.os_id, evento.descricao, evento.ocorrido_em)
        )


class DisponibilidadeTecnicoObserver(ObservadorOS):
    """Mantém o status do técnico coerente com a quantidade de OS ativas dele."""

    def __init__(self, usuarios: UsuarioRepository, ordens: OrdemServicoRepository) -> None:
        self._usuarios = usuarios
        self._ordens = ordens

    def notificar(self, evento: EventoOS) -> None:
        for tecnico_id in evento.tecnicos_afetados:
            tecnico = self._usuarios.obter(tecnico_id)
            if tecnico is None:
                continue
            ativas = self._ordens.listar(FiltroOS(tecnico_id=tecnico_id, apenas_ativas=True))
            novo = StatusTecnico.EM_ATENDIMENTO if ativas else StatusTecnico.DISPONIVEL
            if tecnico.status is not novo:
                tecnico.status = novo
                self._usuarios.atualizar(tecnico)
