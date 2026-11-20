"""Especialidades técnicas e a regra de compatibilidade entre OS e técnico.

Tanto usuários quanto ordens de serviço têm um conjunto de especialidades,
que pode ter várias ou nenhuma:

- OS sem especialidade exigida: qualquer técnico pode atendê-la.
- OS com especialidades: o técnico precisa ter TODAS elas. Uma OS que exige
  "Elétrica" e "Hidráulica" não vai para quem só domina "Elétrica".
- Técnico sem especialidade: atende apenas OS que não exigem especialidade.

O catálogo é uma enumeração. Para incluir uma nova especialidade, basta
acrescentar um membro.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from .excecoes import DadosInvalidos, EspecialidadeIncompativel


class Especialidade(str, Enum):
    MECANICA = "Mecânica"
    ELETRICA = "Elétrica"
    ELETRONICA = "Eletrônica"
    HIDRAULICA = "Hidráulica"
    PNEUMATICA = "Pneumática"
    REFRIGERACAO = "Refrigeração"
    AUTOMACAO = "Automação"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def de_texto(cls, texto: str) -> "Especialidade":
        """Aceita o valor com ou sem acento e em qualquer caixa ('eletrica', 'ELÉTRICA')."""
        alvo = _sem_acento((texto or "").strip().lower())
        for e in cls:
            if _sem_acento(e.value.lower()) == alvo or e.name.lower() == alvo:
                return e
        raise DadosInvalidos(f"Especialidade inválida: {texto!r}")


_ACENTOS = str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc")


def _sem_acento(texto: str) -> str:
    return texto.translate(_ACENTOS)


Especialidades = frozenset[Especialidade]


def normalizar(valores: Iterable[Especialidade | str] | None) -> Especialidades:
    """Converte qualquer coleção (inclusive vazia ou None) em um conjunto imutável."""
    return frozenset(
        v if isinstance(v, Especialidade) else Especialidade.de_texto(v) for v in (valores or ())
    )


def faltantes(exigidas: Especialidades, do_tecnico: Especialidades) -> Especialidades:
    return frozenset(exigidas) - frozenset(do_tecnico)


def compativel(exigidas: Especialidades, do_tecnico: Especialidades) -> bool:
    return not faltantes(exigidas, do_tecnico)


def exigir_compatibilidade(exigidas: Especialidades, do_tecnico: Especialidades,
                           nome_tecnico: str) -> None:
    falta = faltantes(exigidas, do_tecnico)
    if falta:
        raise EspecialidadeIncompativel(
            f"{nome_tecnico} não possui a(s) especialidade(s) exigida(s) pela OS: {rotulo(falta)}."
        )


def ordenar(valores: Iterable[Especialidade]) -> list[Especialidade]:
    ordem = list(Especialidade)
    return sorted(valores, key=ordem.index)


def rotulo(valores: Iterable[Especialidade], vazio: str = "nenhuma") -> str:
    itens = ordenar(valores)
    return ", ".join(e.value for e in itens) if itens else vazio
