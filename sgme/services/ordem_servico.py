"""Casos de uso da Ordem de Serviço."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sgme.domain.entidades import (
    Equipamento, EventoHistorico, FiltroOS, OrdemServico, Usuario,
)
from sgme.domain.excecoes import DadosInvalidos, NaoEncontrado
from sgme.domain.sla import PoliticaSLA, politica_sla
from sgme.domain.status_os import STATUS_OPERACIONAIS_TECNICO, StatusOS
from sgme.repositories.interfaces import (
    EquipamentoRepository, HistoricoRepository, OrdemServicoRepository, UsuarioRepository,
)
from .eventos import EventoOS, PublicadorEventos, TipoEvento
from .permissoes import Acao, FabricaPoliticaAcesso

Relogio = Callable[[], datetime]


@dataclass(frozen=True)
class ResumoOS:
    """Dados prontos para exibição (evita que a interface faça consultas)."""

    ordem: OrdemServico
    equipamento: str
    tecnico: str | None
    sla: PoliticaSLA
    atrasada: bool

    @property
    def prazo(self) -> datetime | None:
        if self.ordem.data_abertura is None:
            return None
        return self.sla.prazo_limite(self.ordem.data_abertura)


@dataclass(frozen=True)
class DetalheOS:
    resumo: ResumoOS
    criador: str
    historico: list[EventoHistorico]


class OrdemServicoService:
    def __init__(
        self,
        ordens: OrdemServicoRepository,
        equipamentos: EquipamentoRepository,
        usuarios: UsuarioRepository,
        historico: HistoricoRepository,
        eventos: PublicadorEventos,
        relogio: Relogio = datetime.now,
    ) -> None:
        self._ordens = ordens
        self._equipamentos = equipamentos
        self._usuarios = usuarios
        self._historico = historico
        self._eventos = eventos
        self._agora = relogio

    # ------------------------------------------------------------ auxiliares
    def _carregar(self, os_id: int) -> OrdemServico:
        ordem = self._ordens.obter(os_id)
        if ordem is None:
            raise NaoEncontrado(f"OS #{os_id} não encontrada.")
        return ordem

    def _salvar_e_publicar(self, ordem: OrdemServico, tipo: TipoEvento, descricao: str,
                           tecnicos: tuple[int | None, ...] = ()) -> OrdemServico:
        self._ordens.atualizar(ordem)
        self._eventos.publicar(EventoOS(
            tipo=tipo, os_id=ordem.id, descricao=descricao, ocorrido_em=self._agora(),
            tecnicos_afetados=tuple(t for t in tecnicos if t is not None),
        ))
        return ordem

    def _resumir(self, ordem: OrdemServico,
                 equipamentos: dict[int, Equipamento] | None = None,
                 usuarios: dict[int, Usuario] | None = None) -> ResumoOS:
        equipamento = (equipamentos or {}).get(ordem.equipamento_id) \
            or self._equipamentos.obter(ordem.equipamento_id)
        tecnico = None
        if ordem.tecnico_id is not None:
            tecnico = (usuarios or {}).get(ordem.tecnico_id) or self._usuarios.obter(ordem.tecnico_id)
        sla = politica_sla(ordem.criticidade)
        return ResumoOS(
            ordem=ordem,
            equipamento=equipamento.nome if equipamento else f"#{ordem.equipamento_id} (removido)",
            tecnico=tecnico.nome if tecnico else None,
            sla=sla,
            atrasada=sla.esta_atrasada(ordem.data_abertura, self._agora(), ordem.finalizada),
        )

    # -------------------------------------------------------------- consultas
    def listar(self, filtro: FiltroOS | None = None) -> list[ResumoOS]:
        equipamentos = {e.id: e for e in self._equipamentos.listar()}
        usuarios = {u.id: u for u in self._usuarios.listar()}
        return [self._resumir(o, equipamentos, usuarios) for o in self._ordens.listar(filtro)]

    def fila_priorizada(self, filtro: FiltroOS | None = None) -> list[ResumoOS]:
        """OS ativas ordenadas por atraso, peso do SLA (Strategy) e antiguidade."""
        filtro = filtro or FiltroOS()
        filtro.apenas_ativas = True
        return sorted(
            self.listar(filtro),
            key=lambda r: (not r.atrasada, -r.sla.peso, r.ordem.id),
        )

    def detalhar(self, os_id: int) -> DetalheOS:
        ordem = self._carregar(os_id)
        criador = self._usuarios.obter(ordem.criador_id)
        return DetalheOS(
            resumo=self._resumir(ordem),
            criador=criador.nome if criador else f"#{ordem.criador_id}",
            historico=self._historico.listar_por_os(os_id),
        )

    # --------------------------------------------------------------- comandos
    def abrir(self, ator: Usuario, equipamento_id: int, falha: str, criticidade: str) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.ABRIR_OS)
        equipamento = self._equipamentos.obter(equipamento_id)
        if equipamento is None:
            raise NaoEncontrado(f"Equipamento #{equipamento_id} não encontrado.")
        if not equipamento.ativo:
            raise DadosInvalidos(f"O equipamento '{equipamento.nome}' está inativo.")
        ordem = OrdemServico(
            equipamento_id=equipamento_id, criador_id=ator.id, falha_apontada=falha,
            criticidade=criticidade, data_abertura=self._agora(),
        )
        self._ordens.adicionar(ordem)
        self._eventos.publicar(EventoOS(
            TipoEvento.ABERTA, ordem.id,
            f"OS aberta por {ator.nome}. Criticidade {ordem.criticidade}. "
            f"Falha reportada: {ordem.falha_apontada}",
            self._agora(),
        ))
        return ordem

    def atribuir(self, ator: Usuario, os_id: int, tecnico_id: int) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.ATRIBUIR_OS)
        ordem = self._carregar(os_id)
        tecnico = self._usuarios.obter(tecnico_id)
        if tecnico is None or not tecnico.eh_tecnico:
            raise DadosInvalidos(f"Usuário #{tecnico_id} não é um técnico válido.")
        anterior = ordem.atribuir(tecnico.id)
        acao = "reatribuída" if anterior else "atribuída"
        return self._salvar_e_publicar(
            ordem, TipoEvento.ATRIBUIDA, f"OS {acao} ao técnico {tecnico.nome} por {ator.nome}.",
            (anterior, tecnico.id),
        )

    def registrar_diagnostico(self, ator: Usuario, os_id: int, diagnostico: str) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.TRABALHAR_OS)
        ordem = self._carregar(os_id)
        ordem.registrar_diagnostico(ator.id, diagnostico)
        return self._salvar_e_publicar(
            ordem, TipoEvento.DIAGNOSTICO, f"Diagnóstico registrado por {ator.nome}: {ordem.diagnostico}",
        )

    def apontar_reparo(self, ator: Usuario, os_id: int, horas: str | float, pecas: str) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.TRABALHAR_OS)
        ordem = self._carregar(os_id)
        antes = ordem.horas_trabalhadas
        ordem.apontar_reparo(ator.id, horas, pecas)
        texto = f"Apontamento de {ator.nome}: {ordem.horas_trabalhadas - antes:g} h"
        if pecas and pecas.strip():
            texto += f"; peças: {pecas.strip()}"
        return self._salvar_e_publicar(ordem, TipoEvento.APONTAMENTO, texto)

    def alterar_status(self, ator: Usuario, os_id: int, novo_status: StatusOS) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.TRABALHAR_OS)
        if novo_status not in STATUS_OPERACIONAIS_TECNICO:
            raise DadosInvalidos(f"O técnico não pode definir o status '{novo_status}'.")
        ordem = self._carregar(os_id)
        anterior = ordem.status
        ordem.alterar_status_operacional(ator.id, novo_status)
        return self._salvar_e_publicar(
            ordem, TipoEvento.STATUS_ALTERADO,
            f"Status alterado de '{anterior}' para '{novo_status}' por {ator.nome}.",
        )

    def encerrar(self, ator: Usuario, os_id: int, aprovar: bool, parecer: str) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.ENCERRAR_OS)
        ordem = self._carregar(os_id)
        ordem.encerrar(aprovar, parecer, self._agora())
        return self._salvar_e_publicar(
            ordem, TipoEvento.ENCERRADA,
            f"Encerramento administrativo ({ordem.status}) por {ator.nome}. Parecer: {ordem.parecer_gestor}",
            (ordem.tecnico_id,),
        )

    def devolver(self, ator: Usuario, os_id: int, parecer: str) -> OrdemServico:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.ENCERRAR_OS)
        ordem = self._carregar(os_id)
        ordem.devolver_para_execucao(parecer)
        return self._salvar_e_publicar(
            ordem, TipoEvento.DEVOLVIDA,
            f"Reparo reprovado por {ator.nome} e devolvido ao técnico. Parecer: {ordem.parecer_gestor}",
            (ordem.tecnico_id,),
        )
