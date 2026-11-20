"""Conversão de objetos do domínio em textos/cores para o terminal."""
from __future__ import annotations

from datetime import datetime

from sgme.domain.entidades import StatusTecnico
from sgme.domain.especialidades import rotulo
from sgme.domain.sla import Criticidade
from sgme.domain.status_os import StatusOS
from sgme.services.ordem_servico import ResumoOS
from .console import Celula, Cor

COR_STATUS = {
    StatusOS.ABERTA: Cor.AZUL,
    StatusOS.EM_ANDAMENTO: Cor.CIANO,
    StatusOS.EM_EXECUCAO: Cor.CIANO,
    StatusOS.AGUARDANDO_PECA: Cor.MAGENTA,
    StatusOS.REPARO_FINALIZADO: Cor.AMARELO,
    StatusOS.CONCLUIDA: Cor.VERDE,
    StatusOS.CANCELADA: Cor.CINZA,
}

COR_CRITICIDADE = {
    Criticidade.ALTA: Cor.VERMELHO,
    Criticidade.MEDIA: Cor.AMARELO,
    Criticidade.BAIXA: Cor.VERDE,
}

COR_TECNICO = {
    StatusTecnico.DISPONIVEL: Cor.VERDE,
    StatusTecnico.EM_ATENDIMENTO: Cor.AMARELO,
}


def data(valor: datetime | None) -> str:
    return valor.strftime("%d/%m/%Y %H:%M") if valor else "—"


def horas(valor: float) -> str:
    return f"{valor:.1f} h".replace(".", ",")


def status(s: StatusOS) -> Celula:
    return (s.value, COR_STATUS.get(s, ""))


def criticidade(c: Criticidade) -> Celula:
    return (c.value, COR_CRITICIDADE.get(c, ""))


def sla(r: ResumoOS) -> Celula:
    if r.ordem.finalizada:
        return ("—", Cor.CINZA)
    if r.atrasada:
        return ("ATRASADA", Cor.VERMELHO + Cor.NEGRITO)
    return (f"até {r.prazo:%d/%m %H:%M}" if r.prazo else "—", "")


def especialidades(valores, vazio: str = "—") -> str:
    return rotulo(valores, vazio)


def linha_os(r: ResumoOS) -> list[Celula]:
    o = r.ordem
    return [f"#{o.id}", r.equipamento, o.falha_apontada,
            (especialidades(o.especialidades, "qualquer"), "" if o.especialidades else Cor.CINZA),
            criticidade(o.criticidade), status(o.status), r.tecnico or "—", sla(r)]
