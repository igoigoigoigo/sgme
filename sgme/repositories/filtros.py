"""Regra de filtragem de OS compartilhada pelas implementações em memória."""
from __future__ import annotations

from sgme.domain.entidades import FiltroOS, OrdemServico


def atende_filtro(ordem: OrdemServico, filtro: FiltroOS | None) -> bool:
    if filtro is None:
        return True
    if filtro.status is not None and ordem.status is not filtro.status:
        return False
    if filtro.criticidade is not None and ordem.criticidade is not filtro.criticidade:
        return False
    if filtro.tecnico_id is not None and ordem.tecnico_id != filtro.tecnico_id:
        return False
    if filtro.equipamento_id is not None and ordem.equipamento_id != filtro.equipamento_id:
        return False
    if filtro.especialidade is not None and filtro.especialidade not in ordem.especialidades:
        return False
    if filtro.apenas_ativas and ordem.finalizada:
        return False
    if filtro.texto:
        alvo = f"{ordem.id} {ordem.falha_apontada} {ordem.diagnostico or ''}".lower()
        if filtro.texto.strip().lower() not in alvo:
            return False
    return True
