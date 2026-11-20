"""Política de atendimento (SLA) por criticidade — padrão Strategy.

Cada criticidade tem um prazo e um peso de prioridade diferentes. O cálculo de
"OS atrasada" e a ordenação da fila usam a estratégia sem `if/elif` espalhados
pelo código: para criar uma criticidade "Emergencial" basta registrar uma nova
estratégia (Aberto/Fechado).
"""
from __future__ import annotations

from abc import ABC
from datetime import datetime, timedelta
from enum import Enum


class Criticidade(str, Enum):
    BAIXA = "Baixa"
    MEDIA = "Média"
    ALTA = "Alta"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def de_texto(cls, texto: str) -> "Criticidade":
        """Normaliza entradas como 'media', 'Media' (formato da Entrega 1) ou 'Média'."""
        normalizado = (texto or "").strip().lower().replace("é", "e")
        for c in cls:
            if c.value.lower().replace("é", "e") == normalizado:
                return c
        raise ValueError(f"Criticidade inválida: {texto!r}")


class PoliticaSLA(ABC):
    criticidade: Criticidade
    prazo: timedelta
    peso: int  # maior = mais urgente

    def prazo_limite(self, abertura: datetime) -> datetime:
        return abertura + self.prazo

    def esta_atrasada(self, abertura: datetime | None, agora: datetime, finalizada: bool) -> bool:
        if finalizada or abertura is None:
            return False
        return agora > self.prazo_limite(abertura)


class SLAAlta(PoliticaSLA):
    criticidade = Criticidade.ALTA
    prazo = timedelta(hours=4)
    peso = 3


class SLAMedia(PoliticaSLA):
    criticidade = Criticidade.MEDIA
    prazo = timedelta(hours=24)
    peso = 2


class SLABaixa(PoliticaSLA):
    criticidade = Criticidade.BAIXA
    prazo = timedelta(hours=72)
    peso = 1


_POLITICAS: dict[Criticidade, PoliticaSLA] = {
    p.criticidade: p() for p in (SLAAlta, SLAMedia, SLABaixa)
}


def politica_sla(criticidade: Criticidade | str) -> PoliticaSLA:
    if not isinstance(criticidade, Criticidade):
        criticidade = Criticidade.de_texto(criticidade)
    return _POLITICAS[criticidade]
