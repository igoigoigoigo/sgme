"""Menu dinâmico — padrão Command.

Na Entrega 1 havia dois menus quase idênticos (`menu_gestor` e
`menu_tecnico`) com cadeias de `if/elif`. Para incluir uma opção era preciso
editar ambos e renumerar tudo à mão.

Agora cada opção é um objeto `Comando` (rótulo + ação executável + permissão
exigida). O menu é montado a partir da política de acesso do usuário logado,
numerado automaticamente e agrupado por seção. Nova funcionalidade = nova
entrada na lista `COMANDOS`, sem alterar o laço do menu (Aberto/Fechado).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sgme.domain.especialidades import rotulo
from sgme.domain.excecoes import ErroDominio
from sgme.services.permissoes import Acao
from . import telas
from .console import Cancelado, Cor
from .telas import Sessao


@dataclass(frozen=True)
class Comando:
    grupo: str
    rotulo: str
    executar: Callable[[Sessao], None]
    requer: Acao | None = None
    somente: Acao | None = None  # exibido só para quem tem esta ação (ex.: "Minhas OS")

    def disponivel_para(self, sessao: Sessao) -> bool:
        politica = sessao.politica
        exigida = self.requer or self.somente
        return exigida is None or politica.pode(exigida)


COMANDOS: list[Comando] = [
    Comando("Ordens de serviço", "Painel resumo", telas.painel),
    Comando("Ordens de serviço", "Minhas OS ativas", telas.minhas_os, somente=Acao.TRABALHAR_OS),
    Comando("Ordens de serviço", "Fila priorizada por SLA", telas.fila_priorizada, somente=Acao.ATRIBUIR_OS),
    Comando("Ordens de serviço", "Consultar OS (filtros)", telas.listar_os),
    Comando("Ordens de serviço", "Detalhes e histórico de uma OS", telas.detalhes_os),
    Comando("Ordens de serviço", "Abrir novo chamado", telas.abrir_chamado, Acao.ABRIR_OS),
    Comando("Gestão", "Atribuir / reatribuir técnico", telas.atribuir_os, Acao.ATRIBUIR_OS),
    Comando("Gestão", "Definir especialidades exigidas da OS", telas.definir_especialidades_os,
            Acao.ATRIBUIR_OS),
    Comando("Gestão", "Aprovar, devolver ou cancelar OS", telas.encerrar_os, Acao.ENCERRAR_OS),
    Comando("Trabalho técnico", "Registrar diagnóstico", telas.registrar_diagnostico, Acao.TRABALHAR_OS),
    Comando("Trabalho técnico", "Apontar horas e peças", telas.apontar_reparo, Acao.TRABALHAR_OS),
    Comando("Trabalho técnico", "Atualizar status operacional", telas.alterar_status, Acao.TRABALHAR_OS),
    Comando("Cadastros", "Listar equipamentos", telas.listar_equipamentos),
    Comando("Cadastros", "Cadastrar equipamento", telas.cadastrar_equipamento, Acao.GERENCIAR_EQUIPAMENTOS),
    Comando("Cadastros", "Editar equipamento", telas.editar_equipamento, Acao.GERENCIAR_EQUIPAMENTOS),
    Comando("Cadastros", "Ativar / inativar equipamento", telas.ativar_inativar_equipamento,
            Acao.GERENCIAR_EQUIPAMENTOS),
    Comando("Cadastros", "Disponibilidade da equipe", telas.equipe),
    Comando("Cadastros", "Cadastrar usuário", telas.cadastrar_usuario, Acao.GERENCIAR_USUARIOS),
    Comando("Cadastros", "Definir especialidades de usuário", telas.definir_especialidades_usuario,
            Acao.GERENCIAR_USUARIOS),
]


class Menu:
    def __init__(self, sessao: Sessao, comandos: list[Comando] | None = None) -> None:
        self._s = sessao
        self._comandos = [c for c in (comandos or COMANDOS) if c.disponivel_para(sessao)]

    def _exibir(self) -> None:
        con = self._s.console
        grupo_atual = None
        for i, cmd in enumerate(self._comandos, start=1):
            if cmd.grupo != grupo_atual:
                grupo_atual = cmd.grupo
                con.escrever(con.pintar(f"\n  {grupo_atual.upper()}", Cor.NEGRITO, Cor.AZUL))
            con.escrever(f"   {con.pintar(str(i).rjust(2), Cor.CIANO)}  {cmd.rotulo}")
        con.escrever(con.pintar("\n  SESSÃO", Cor.NEGRITO, Cor.AZUL))
        con.escrever(f"   {con.pintar(' T', Cor.CIANO)}  Trocar usuário")
        con.escrever(f"   {con.pintar(' 0', Cor.CIANO)}  Sair do sistema")

    def executar(self) -> str:
        """Laço principal. Retorna 'trocar' ou 'sair'."""
        con = self._s.console
        while True:
            self._s.recarregar_usuario()
            u = self._s.usuario
            con.limpar()
            con.cabecalho("SGME · Gestão de Manutenção",
                          f"{u.nome} · {u.perfil}"
                          + (f" · {u.status} · {rotulo(u.especialidades, 'sem especialidade')}"
                             if u.eh_tecnico else ""))
            self._exibir()
            con.escrever()
            try:
                escolha = con.texto("Escolha uma opção").lower()
            except Cancelado:
                continue
            if escolha == "0":
                return "sair"
            if escolha == "t":
                return "trocar"
            if not escolha.isdigit() or not 1 <= int(escolha) <= len(self._comandos):
                con.erro("Opção inválida.")
                con.pausar()
                continue
            self._rodar(self._comandos[int(escolha) - 1])

    def _rodar(self, cmd: Comando) -> None:
        con = self._s.console
        con.limpar()
        con.cabecalho(cmd.rotulo, cmd.grupo)
        con.info("  (Enter vazio em qualquer pergunta cancela a operação)")
        try:
            cmd.executar(self._s)
        except Cancelado:
            con.info("\n  Operação cancelada.")
        except ErroDominio as erro:
            con.erro(str(erro))
        con.pausar()
