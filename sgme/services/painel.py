"""Indicadores do painel (dashboard) exibido ao entrar no sistema."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sgme.domain.entidades import Usuario
from sgme.domain.sla import Criticidade
from sgme.domain.status_os import StatusOS
from .cadastros import UsuarioService
from .ordem_servico import OrdemServicoService, ResumoOS


@dataclass(frozen=True)
class Painel:
    por_status: dict[StatusOS, int]
    ativas_por_criticidade: dict[Criticidade, int]
    atrasadas: list[ResumoOS]
    tecnicos: list[Usuario]
    horas_totais: float
    total: int

    @property
    def ativas(self) -> int:
        return sum(q for s, q in self.por_status.items()
                   if s not in (StatusOS.CONCLUIDA, StatusOS.CANCELADA))


class PainelService:
    def __init__(self, ordens: OrdemServicoService, usuarios: UsuarioService) -> None:
        self._ordens = ordens
        self._usuarios = usuarios

    def gerar(self, tecnico_id: int | None = None) -> Painel:
        resumos = self._ordens.listar()
        if tecnico_id is not None:
            resumos = [r for r in resumos if r.ordem.tecnico_id == tecnico_id]
        por_status = Counter(r.ordem.status for r in resumos)
        ativas = [r for r in resumos if not r.ordem.finalizada]
        return Painel(
            por_status={s: por_status.get(s, 0) for s in StatusOS},
            ativas_por_criticidade={
                c: sum(1 for r in ativas if r.ordem.criticidade is c) for c in Criticidade
            },
            atrasadas=[r for r in ativas if r.atrasada],
            tecnicos=self._usuarios.listar_tecnicos(),
            horas_totais=sum(r.ordem.horas_trabalhadas for r in resumos),
            total=len(resumos),
        )
