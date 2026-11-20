"""Telas da CLI. Cada função recebe a sessão, conversa com o usuário e chama
um serviço. Nenhuma tela acessa o banco diretamente."""
from __future__ import annotations

from dataclasses import dataclass

from sgme.container import Container
from sgme.domain.entidades import FiltroOS, Perfil, StatusTecnico, Usuario
from sgme.domain.especialidades import Especialidade, rotulo
from sgme.domain.sla import Criticidade, politica_sla
from sgme.domain.status_os import STATUS_OPERACIONAIS_TECNICO, StatusOS, estado_de
from sgme.services.ordem_servico import ResumoOS
from sgme.services.permissoes import FabricaPoliticaAcesso, PoliticaAcesso
from . import formatacao as fmt
from .console import Cancelado, Coluna, Console, Cor

COLUNAS_OS = [
    Coluna("OS", 4, direita=True), Coluna("Equipamento", 10, flex=True),
    Coluna("Falha", 10, flex=True), Coluna("Especialidades", 8, flex=True),
    Coluna("Criticid.", 5), Coluna("Status", 6),
    Coluna("Técnico", 7, flex=True), Coluna("SLA", 8),
]


@dataclass
class Sessao:
    usuario: Usuario
    container: Container
    console: Console

    @property
    def politica(self) -> PoliticaAcesso:
        return FabricaPoliticaAcesso.criar(self.usuario)

    def recarregar_usuario(self) -> None:
        self.usuario = self.container.usuarios.obter(self.usuario.id)


# ----------------------------------------------------------------- auxiliares
def _tabela_os(con: Console, resumos: list[ResumoOS], vazio: str = "Nenhuma OS encontrada.") -> None:
    con.tabela(COLUNAS_OS, [fmt.linha_os(r) for r in resumos], vazio)


def _selecionar_os(s: Sessao, resumos: list[ResumoOS], titulo: str) -> int:
    con = s.console
    con.secao(titulo)
    _tabela_os(con, resumos)
    if not resumos:
        raise Cancelado()
    return con.inteiro("Número da OS", {r.ordem.id for r in resumos})


def _escolher_criticidade(con: Console) -> Criticidade:
    opcoes = [
        (f"{con.pintar(c.value.ljust(6), fmt.COR_CRITICIDADE[c])} atendimento em até "
         f"{int(politica_sla(c).prazo.total_seconds() // 3600)} h", c)
        for c in (Criticidade.ALTA, Criticidade.MEDIA, Criticidade.BAIXA)
    ]
    return con.escolher("Criticidade", opcoes)


def _escolher_especialidades(con: Console, prompt: str,
                             atuais: frozenset[Especialidade] | None = None) -> list[Especialidade]:
    return con.escolher_varios(prompt, [(e.value, e) for e in Especialidade], atuais)


def _tabela_tecnicos(con: Console, linhas: list[tuple[Usuario, frozenset | None]], ativas) -> None:
    """Tabela da equipe. Se `faltantes` vier preenchido, mostra a compatibilidade com a OS."""
    colunas = [Coluna("ID", 3, direita=True), Coluna("Nome", 8, flex=True),
               Coluna("Especialidades", 10, flex=True), Coluna("Status", 10),
               Coluna("OS ativas", 3, direita=True)]
    com_compat = any(f is not None for _, f in linhas)
    if com_compat:
        colunas.append(Coluna("Compatível com a OS", 10, flex=True))
    tabela = []
    for t, falta in linhas:
        linha = [f"#{t.id}", t.nome, (fmt.especialidades(t.especialidades, "nenhuma"),
                                      "" if t.especialidades else Cor.CINZA),
                 (t.status.value, fmt.COR_TECNICO[t.status]),
                 str(sum(1 for r in ativas if r.ordem.tecnico_id == t.id))]
        if com_compat:
            linha.append(("✔ sim", Cor.VERDE) if not falta
                         else (f"✖ falta {rotulo(falta)}", Cor.VERMELHO))
        tabela.append(linha)
    con.tabela(colunas, tabela, "Nenhum técnico cadastrado.")


# ------------------------------------------------------------------- painel
def painel(s: Sessao) -> None:
    con = s.console
    tecnico_id = s.usuario.id if s.usuario.eh_tecnico else None
    p = s.container.painel.gerar(tecnico_id)
    escopo = "minhas OS" if tecnico_id else "todas as OS"
    con.secao(f"Painel ({escopo})")

    cartoes = [
        ("Ativas", str(p.ativas), Cor.CIANO),
        ("Atrasadas", str(len(p.atrasadas)), Cor.VERMELHO if p.atrasadas else Cor.VERDE),
        ("Aguard. peça", str(p.por_status[StatusOS.AGUARDANDO_PECA]), Cor.MAGENTA),
        ("P/ aprovação", str(p.por_status[StatusOS.REPARO_FINALIZADO]), Cor.AMARELO),
        ("Concluídas", str(p.por_status[StatusOS.CONCLUIDA]), Cor.VERDE),
        ("Horas", fmt.horas(p.horas_totais), Cor.AZUL),
    ]
    por_linha = 3 if con.largura < 100 else 6
    for i in range(0, len(cartoes), por_linha):
        grupo = cartoes[i:i + por_linha]
        con.escrever("  " + "   ".join(con.pintar(f"{r}:", Cor.CINZA) + " "
                                       + con.pintar(v, Cor.NEGRITO, c) for r, v, c in grupo))

    con.escrever()
    maior = max(p.ativas_por_criticidade.values(), default=0) or 1
    for c in (Criticidade.ALTA, Criticidade.MEDIA, Criticidade.BAIXA):
        qtd = p.ativas_por_criticidade[c]
        barra = "█" * round(20 * qtd / maior) if qtd else ""
        con.escrever(f"  {c.value.ljust(6)} {con.pintar(barra, fmt.COR_CRITICIDADE[c])} {qtd}")

    if p.atrasadas:
        con.escrever()
        con.aviso("OS com prazo de atendimento estourado:")
        _tabela_os(con, p.atrasadas)

    if s.usuario.perfil is Perfil.GESTOR:
        livres = sum(1 for t in p.tecnicos if t.status is StatusTecnico.DISPONIVEL)
        con.escrever()
        con.info(f"  Técnicos disponíveis: {livres} de {len(p.tecnicos)}")


# ---------------------------------------------------------------- consultas
def listar_os(s: Sessao) -> None:
    con = s.console
    con.secao("Consultar ordens de serviço")
    filtro = con.escolher("Filtro", [
        ("Somente ativas", FiltroOS(apenas_ativas=True)),
        ("Todas", FiltroOS()),
        ("Por status", "status"),
        ("Por criticidade", "criticidade"),
        ("Por especialidade exigida", "especialidade"),
        ("Buscar texto (nº, falha ou diagnóstico)", "texto"),
    ])
    if filtro == "status":
        filtro = FiltroOS(status=con.escolher("Status", [(st.value, st) for st in StatusOS]))
    elif filtro == "criticidade":
        filtro = FiltroOS(criticidade=_escolher_criticidade(con))
    elif filtro == "especialidade":
        filtro = FiltroOS(especialidade=con.escolher(
            "Especialidade", [(e.value, e) for e in Especialidade]))
    elif filtro == "texto":
        filtro = FiltroOS(texto=con.texto("Texto"))
    resumos = s.container.ordens.listar(filtro)
    con.escrever()
    _tabela_os(con, resumos)
    con.info(f"  {len(resumos)} OS listada(s).")


def fila_priorizada(s: Sessao) -> None:
    con = s.console
    con.secao("Fila de atendimento priorizada (atraso › criticidade › antiguidade)")
    _tabela_os(con, s.container.ordens.fila_priorizada(), "Nenhuma OS ativa.")


def minhas_os(s: Sessao) -> None:
    con = s.console
    con.secao("Minhas OS ativas")
    resumos = s.container.ordens.fila_priorizada(FiltroOS(tecnico_id=s.usuario.id))
    _tabela_os(con, resumos, "Você não possui OS ativas.")


def detalhes_os(s: Sessao) -> None:
    con = s.console
    os_id = con.inteiro("Número da OS")
    d = s.container.ordens.detalhar(os_id)
    r, o = d.resumo, d.resumo.ordem
    con.secao(f"OS #{o.id} — {r.equipamento}")
    con.campo("Status", o.status.value, fmt.COR_STATUS[o.status])
    con.campo("Criticidade", o.criticidade.value, fmt.COR_CRITICIDADE[o.criticidade])
    con.campo("Especialidades", rotulo(o.especialidades, "nenhuma exigida (qualquer técnico)"))
    sla_txt, sla_cor = fmt.sla(r)
    con.campo("SLA", sla_txt, sla_cor)
    con.campo("Aberta por", f"{d.criador} em {fmt.data(o.data_abertura)}")
    con.campo("Técnico", r.tecnico)
    con.campo("Falha", o.falha_apontada)
    con.campo("Diagnóstico", o.diagnostico)
    con.campo("Horas", fmt.horas(o.horas_trabalhadas))
    con.campo("Peças", o.pecas_utilizadas)
    con.campo("Parecer gestor", o.parecer_gestor)
    if o.data_encerramento:
        con.campo("Encerrada em", fmt.data(o.data_encerramento))
    proximos = ", ".join(st.value for st in StatusOS if estado_de(o.status).pode_ir_para(st))
    con.campo("Próximos status", proximos or "nenhum (OS finalizada)")

    con.secao("Histórico")
    for ev in d.historico:
        con.escrever(f"  {con.pintar(fmt.data(ev.data_hora), Cor.CINZA)}  {con.pintar('●', Cor.CIANO)} {ev.descricao}")
    if not d.historico:
        con.info("  Sem eventos registrados.")


def listar_equipamentos(s: Sessao) -> None:
    con = s.console
    con.secao("Equipamentos")
    ativas = s.container.ordens.listar(FiltroOS(apenas_ativas=True))
    con.tabela(
        [Coluna("ID", 3, direita=True), Coluna("Nome", 8, flex=True),
         Coluna("Descrição", 10, flex=True), Coluna("Situação", 8), Coluna("OS ativas", 3, direita=True)],
        [[f"#{e.id}", e.nome, e.descricao or "—",
          ("Ativo", Cor.VERDE) if e.ativo else ("Inativo", Cor.CINZA),
          str(sum(1 for r in ativas if r.ordem.equipamento_id == e.id))]
         for e in s.container.equipamentos.listar()],
    )


def equipe(s: Sessao) -> None:
    con = s.console
    con.secao("Disponibilidade da equipe técnica")
    ativas = s.container.ordens.listar(FiltroOS(apenas_ativas=True))
    _tabela_tecnicos(con, [(t, None) for t in s.container.usuarios.listar_tecnicos()], ativas)


# --------------------------------------------------------------- comandos OS
def abrir_chamado(s: Sessao) -> None:
    con = s.console
    con.secao("Abrir novo chamado")
    equipamentos = s.container.equipamentos.listar(apenas_ativos=True)
    if not equipamentos:
        con.aviso("Não há equipamentos ativos cadastrados.")
        return
    eq_id = con.escolher("Equipamento", [(f"{e.nome} {con.pintar('— ' + e.descricao, Cor.CINZA)}", e.id)
                                         for e in equipamentos])
    falha = con.texto("Descrição da falha")
    crit = _escolher_criticidade(con)
    esp = _escolher_especialidades(con, "Especialidades exigidas")
    ordem = s.container.ordens.abrir(s.usuario, eq_id, falha, crit.value, esp)
    con.sucesso(f"Chamado aberto: OS #{ordem.id} ({ordem.criticidade}; "
                f"especialidades: {rotulo(ordem.especialidades)}).")


def atribuir_os(s: Sessao) -> None:
    con = s.console
    pendentes = [r for r in s.container.ordens.fila_priorizada()
                 if r.ordem.estado.aceita_atribuicao]
    os_id = _selecionar_os(s, pendentes, "OS que aceitam atribuição")
    ordem = next(r.ordem for r in pendentes if r.ordem.id == os_id)
    candidatos = s.container.ordens.tecnicos_para(os_id)
    con.secao(f"Técnicos para a OS #{os_id} · exige: "
              f"{rotulo(ordem.especialidades, 'nenhuma especialidade')}")
    _tabela_tecnicos(con, candidatos, s.container.ordens.listar(FiltroOS(apenas_ativas=True)))
    if not any(not falta for _, falta in candidatos):
        con.aviso("Nenhum técnico possui todas as especialidades exigidas. "
                  "Ajuste as especialidades da OS ou do técnico.")
        return
    tec_id = con.inteiro("ID do técnico", {t.id for t, _ in candidatos})
    s.container.ordens.atribuir(s.usuario, os_id, tec_id)
    con.sucesso(f"OS #{os_id} atribuída.")


def definir_especialidades_os(s: Sessao) -> None:
    con = s.console
    ativas = s.container.ordens.fila_priorizada()
    os_id = _selecionar_os(s, ativas, "OS ativas")
    ordem = next(r for r in ativas if r.ordem.id == os_id)
    con.info(f"  Atuais: {rotulo(ordem.ordem.especialidades)}"
             + (f" · técnico atribuído: {ordem.tecnico}" if ordem.tecnico else ""))
    novas = _escolher_especialidades(con, "Especialidades exigidas", ordem.ordem.especialidades)
    atualizada = s.container.ordens.definir_especialidades(s.usuario, os_id, novas)
    con.sucesso(f"OS #{os_id} agora exige: {rotulo(atualizada.especialidades)}.")


def encerrar_os(s: Sessao) -> None:
    con = s.console
    candidatas = [r for r in s.container.ordens.fila_priorizada()]
    candidatas.sort(key=lambda r: r.ordem.status is not StatusOS.REPARO_FINALIZADO)
    os_id = _selecionar_os(s, candidatas, "Encerramento administrativo (reparos finalizados primeiro)")
    ordem = s.container.ordens.detalhar(os_id).resumo.ordem
    opcoes = []
    if ordem.estado.pode_ir_para(StatusOS.CONCLUIDA):
        opcoes.append(("Aprovar e concluir", "aprovar"))
        opcoes.append(("Reprovar e devolver ao técnico", "devolver"))
    opcoes.append(("Cancelar a OS", "cancelar"))
    acao = con.escolher("Ação", opcoes)
    parecer = con.texto("Parecer administrativo")
    if acao == "devolver":
        s.container.ordens.devolver(s.usuario, os_id, parecer)
        con.sucesso(f"OS #{os_id} devolvida para execução.")
        return
    if acao == "cancelar" and not con.confirmar(f"Confirmar cancelamento da OS #{os_id}?"):
        con.info("  Operação abandonada.")
        return
    ordem = s.container.ordens.encerrar(s.usuario, os_id, acao == "aprovar", parecer)
    con.sucesso(f"OS #{os_id} {ordem.status.value.lower()}.")


def _minhas_em_trabalho(s: Sessao, titulo: str) -> int:
    resumos = [r for r in s.container.ordens.fila_priorizada(FiltroOS(tecnico_id=s.usuario.id))
               if r.ordem.estado.aceita_trabalho_tecnico]
    return _selecionar_os(s, resumos, titulo)


def registrar_diagnostico(s: Sessao) -> None:
    os_id = _minhas_em_trabalho(s, "Registrar diagnóstico")
    texto = s.console.texto("Diagnóstico e causa-raiz")
    s.container.ordens.registrar_diagnostico(s.usuario, os_id, texto)
    s.console.sucesso("Diagnóstico salvo.")


def apontar_reparo(s: Sessao) -> None:
    con = s.console
    os_id = _minhas_em_trabalho(s, "Apontamento de reparo")
    horas = con.decimal("Horas trabalhadas (ex.: 2,5)")
    pecas = con.texto("Peças/materiais utilizados (opcional)", obrigatorio=False)
    ordem = s.container.ordens.apontar_reparo(s.usuario, os_id, horas, pecas)
    con.sucesso(f"Apontamento registrado. Total na OS: {fmt.horas(ordem.horas_trabalhadas)}.")


def alterar_status(s: Sessao) -> None:
    con = s.console
    resumos = [r for r in s.container.ordens.fila_priorizada(FiltroOS(tecnico_id=s.usuario.id))
               if any(r.ordem.estado.pode_ir_para(st) for st in STATUS_OPERACIONAIS_TECNICO)]
    os_id = _selecionar_os(s, resumos, "Atualizar status operacional")
    ordem = next(r.ordem for r in resumos if r.ordem.id == os_id)
    permitidos = [st for st in STATUS_OPERACIONAIS_TECNICO if ordem.estado.pode_ir_para(st)]
    novo = con.escolher("Novo status", [(con.pintar(st.value, fmt.COR_STATUS[st]), st) for st in permitidos])
    s.container.ordens.alterar_status(s.usuario, os_id, novo)
    con.sucesso(f"OS #{os_id} agora está '{novo}'.")


# ---------------------------------------------------------------- cadastros
def cadastrar_equipamento(s: Sessao) -> None:
    con = s.console
    con.secao("Cadastrar equipamento")
    nome = con.texto("Nome")
    descricao = con.texto("Descrição (opcional)", obrigatorio=False)
    e = s.container.equipamentos.cadastrar(s.usuario, nome, descricao)
    con.sucesso(f"Equipamento #{e.id} cadastrado.")


def editar_equipamento(s: Sessao) -> None:
    con = s.console
    listar_equipamentos(s)
    ids = {e.id for e in s.container.equipamentos.listar()}
    eq_id = con.inteiro("ID do equipamento", ids)
    atual = s.container.equipamentos.obter(eq_id)
    nome = con.texto("Nome", padrao=atual.nome)
    descricao = con.texto("Descrição", padrao=atual.descricao or "", obrigatorio=False)
    s.container.equipamentos.editar(s.usuario, eq_id, nome, descricao)
    con.sucesso("Equipamento atualizado.")


def ativar_inativar_equipamento(s: Sessao) -> None:
    con = s.console
    listar_equipamentos(s)
    ids = {e.id for e in s.container.equipamentos.listar()}
    eq_id = con.inteiro("ID do equipamento", ids)
    e = s.container.equipamentos.alternar_ativo(s.usuario, eq_id)
    con.sucesso(f"'{e.nome}' agora está {'ativo' if e.ativo else 'inativo'}.")


def cadastrar_usuario(s: Sessao) -> None:
    con = s.console
    con.secao("Cadastrar usuário")
    nome = con.texto("Nome")
    perfil = con.escolher("Perfil", [(p.value, p.value) for p in Perfil])
    esp = _escolher_especialidades(con, "Especialidades")
    u = s.container.usuarios.cadastrar(s.usuario, nome, perfil, esp)
    con.sucesso(f"Usuário #{u.id} ({u.perfil}) cadastrado · especialidades: {rotulo(u.especialidades)}.")


def definir_especialidades_usuario(s: Sessao) -> None:
    con = s.console
    con.secao("Usuários")
    usuarios = s.container.usuarios.listar()
    con.tabela(
        [Coluna("ID", 3, direita=True), Coluna("Nome", 8, flex=True), Coluna("Perfil", 7),
         Coluna("Especialidades", 10, flex=True)],
        [[f"#{u.id}", u.nome, u.perfil.value,
          (fmt.especialidades(u.especialidades, "nenhuma"), "" if u.especialidades else Cor.CINZA)]
         for u in usuarios],
    )
    usuario_id = con.inteiro("ID do usuário", {u.id for u in usuarios})
    atual = next(u for u in usuarios if u.id == usuario_id)
    novas = _escolher_especialidades(con, "Especialidades", atual.especialidades)
    u = s.container.usuarios.definir_especialidades(s.usuario, usuario_id, novas)
    con.sucesso(f"{u.nome}: {rotulo(u.especialidades)}.")
