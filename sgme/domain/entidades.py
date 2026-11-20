"""Entidades do domínio.

Na Entrega 1 os dados circulavam como tuplas do SQLite (`os_data[6]`,
`usuario[1]`), o que acoplava toda a aplicação à ordem das colunas. Agora cada
conceito é uma classe com nome, tipo e invariantes próprios.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .especialidades import Especialidade, Especialidades, exigir_compatibilidade, normalizar
from .excecoes import DadosInvalidos, TransicaoInvalida
from .sla import Criticidade
from .status_os import StatusOS, estado_de, EstadoOS

FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


class Perfil(str, Enum):
    GESTOR = "Gestor"
    TECNICO = "Técnico"

    def __str__(self) -> str:
        return self.value


class StatusTecnico(str, Enum):
    DISPONIVEL = "Disponível"
    EM_ATENDIMENTO = "Em Atendimento"

    def __str__(self) -> str:
        return self.value


def _texto_obrigatorio(valor: str | None, campo: str, maximo: int = 500) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise DadosInvalidos(f"O campo '{campo}' é obrigatório.")
    if len(valor) > maximo:
        raise DadosInvalidos(f"O campo '{campo}' aceita no máximo {maximo} caracteres.")
    return valor


@dataclass
class Usuario:
    nome: str
    perfil: Perfil
    status: StatusTecnico = StatusTecnico.DISPONIVEL
    id: int | None = None
    especialidades: Especialidades = frozenset()  # zero, uma ou várias

    def __post_init__(self) -> None:
        self.nome = _texto_obrigatorio(self.nome, "nome", 100)
        self.perfil = Perfil(self.perfil)
        self.status = StatusTecnico(self.status)
        self.especialidades = normalizar(self.especialidades)

    @property
    def eh_tecnico(self) -> bool:
        return self.perfil is Perfil.TECNICO

    @property
    def iniciais(self) -> str:
        partes = self.nome.split()
        return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


@dataclass
class Equipamento:
    nome: str
    descricao: str = ""
    ativo: bool = True
    id: int | None = None

    def __post_init__(self) -> None:
        self.nome = _texto_obrigatorio(self.nome, "nome", 100)
        self.descricao = (self.descricao or "").strip()[:500]
        self.ativo = bool(self.ativo)


@dataclass(frozen=True)
class EventoHistorico:
    os_id: int
    descricao: str
    data_hora: datetime
    id: int | None = None


@dataclass
class OrdemServico:
    """Agregado principal. Toda mudança de estado passa por métodos que
    consultam o objeto-estado (padrão State) antes de alterar os dados."""

    equipamento_id: int
    criador_id: int
    falha_apontada: str
    criticidade: Criticidade
    status: StatusOS = StatusOS.ABERTA
    tecnico_id: int | None = None
    diagnostico: str | None = None
    horas_trabalhadas: float = 0.0
    pecas_utilizadas: str | None = None
    parecer_gestor: str | None = None
    data_abertura: datetime | None = None
    data_encerramento: datetime | None = None
    id: int | None = None
    especialidades: Especialidades = frozenset()  # exigidas do técnico; vazio = qualquer um

    def __post_init__(self) -> None:
        self.especialidades = normalizar(self.especialidades)
        self.falha_apontada = _texto_obrigatorio(self.falha_apontada, "falha apontada", 1000)
        if not isinstance(self.criticidade, Criticidade):
            try:
                self.criticidade = Criticidade.de_texto(self.criticidade)
            except ValueError as exc:
                raise DadosInvalidos(str(exc)) from exc
        self.status = StatusOS(self.status)
        self.horas_trabalhadas = float(self.horas_trabalhadas or 0.0)

    # ---- consultas -------------------------------------------------------
    @property
    def estado(self) -> EstadoOS:
        return estado_de(self.status)

    @property
    def finalizada(self) -> bool:
        return self.estado.final

    # ---- comandos --------------------------------------------------------
    def _transitar(self, destino: StatusOS) -> None:
        if not self.estado.pode_ir_para(destino):
            raise TransicaoInvalida(
                f"A OS #{self.id} está '{self.status}' e não pode ir para '{destino}'."
            )
        self.status = destino

    def atribuir(self, tecnico: "Usuario") -> int | None:
        """Atribui (ou reatribui) o técnico. Retorna o id do técnico anterior.

        Bloqueia técnicos que não possuem todas as especialidades exigidas."""
        if not self.estado.aceita_atribuicao:
            raise TransicaoInvalida(
                f"Não é possível atribuir técnico a uma OS '{self.status}'."
            )
        if not tecnico.eh_tecnico:
            raise DadosInvalidos(f"{tecnico.nome} não é um técnico.")
        anterior = self.tecnico_id
        if anterior == tecnico.id:
            raise DadosInvalidos("Este técnico já está atribuído a esta OS.")
        exigir_compatibilidade(self.especialidades, tecnico.especialidades, tecnico.nome)
        self.tecnico_id = tecnico.id
        if self.status is StatusOS.ABERTA:
            self._transitar(StatusOS.EM_ANDAMENTO)
        return anterior

    def _exigir_trabalho_do_tecnico(self, tecnico_id: int) -> None:
        if self.tecnico_id != tecnico_id:
            raise TransicaoInvalida("Somente o técnico atribuído pode trabalhar nesta OS.")
        if not self.estado.aceita_trabalho_tecnico:
            raise TransicaoInvalida(
                f"A OS está '{self.status}' e não aceita registros técnicos."
            )

    def registrar_diagnostico(self, tecnico_id: int, diagnostico: str) -> None:
        self._exigir_trabalho_do_tecnico(tecnico_id)
        self.diagnostico = _texto_obrigatorio(diagnostico, "diagnóstico", 2000)

    def apontar_reparo(self, tecnico_id: int, horas: float, pecas: str | None) -> None:
        self._exigir_trabalho_do_tecnico(tecnico_id)
        try:
            horas = float(str(horas).replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise DadosInvalidos("Horas trabalhadas deve ser um número (ex.: 2.5).") from exc
        if not 0 < horas <= 24:
            raise DadosInvalidos("Horas por apontamento devem estar entre 0 e 24.")
        self.horas_trabalhadas = round(self.horas_trabalhadas + horas, 2)
        pecas = (pecas or "").strip()
        if pecas:  # Entrega 1 sobrescrevia as peças anteriores; agora acumula
            self.pecas_utilizadas = (
                f"{self.pecas_utilizadas}; {pecas}" if self.pecas_utilizadas else pecas
            )

    def alterar_status_operacional(self, tecnico_id: int, novo: StatusOS) -> None:
        if self.tecnico_id != tecnico_id:
            raise TransicaoInvalida("Somente o técnico atribuído pode alterar o status.")
        self._transitar(novo)

    def encerrar(self, aprovar: bool, parecer: str, agora: datetime) -> None:
        self.parecer_gestor = _texto_obrigatorio(parecer, "parecer", 1000)
        self._transitar(StatusOS.CONCLUIDA if aprovar else StatusOS.CANCELADA)
        self.data_encerramento = agora

    def definir_especialidades(self, novas, tecnico_atual: "Usuario | None") -> None:
        """Altera as especialidades exigidas. Se já houver técnico atribuído,
        ele precisa continuar compatível; caso contrário a alteração é bloqueada."""
        if self.finalizada:
            raise TransicaoInvalida("Não é possível alterar especialidades de uma OS finalizada.")
        novas = normalizar(novas)
        if tecnico_atual is not None:
            exigir_compatibilidade(novas, tecnico_atual.especialidades, tecnico_atual.nome)
        self.especialidades = novas

    def devolver_para_execucao(self, parecer: str) -> None:
        """Gestor reprova o reparo finalizado e devolve ao técnico."""
        if self.status is not StatusOS.REPARO_FINALIZADO:
            raise TransicaoInvalida("Só é possível devolver uma OS com reparo finalizado.")
        self.parecer_gestor = _texto_obrigatorio(parecer, "parecer", 1000)
        self._transitar(StatusOS.EM_EXECUCAO)


@dataclass
class FiltroOS:
    """Critérios de busca de OS (objeto de consulta, evita listas de parâmetros)."""

    status: StatusOS | None = None
    criticidade: Criticidade | None = None
    tecnico_id: int | None = None
    equipamento_id: int | None = None
    especialidade: Especialidade | None = None  # OS que exigem esta especialidade
    texto: str | None = None
    apenas_ativas: bool = False
