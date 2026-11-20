"""Inicialização da CLI: login e laço de sessão."""
from __future__ import annotations

from sgme.container import Container
from sgme.domain.entidades import Usuario
from .console import Cancelado, Console, Cor, FimDaEntrada
from .menu import Menu
from .telas import Sessao, painel


def _login(container: Container, con: Console) -> Usuario | None:
    con.limpar()
    con.cabecalho("SGME · Sistema de Gestão de Manutenção de Equipamentos", "Entrega 2")
    con.secao("Selecione o usuário para entrar")
    usuarios = container.usuarios.listar()
    opcoes = [
        (f"{u.nome.ljust(20)} {con.pintar(u.perfil.value, Cor.CINZA)}", u) for u in usuarios
    ]
    try:
        return con.escolher("Usuário (Enter para sair)", opcoes)
    except Cancelado:
        return None


def executar(container: Container, con: Console | None = None) -> None:
    con = con or Console()
    try:
        while True:
            usuario = _login(container, con)
            if usuario is None:
                break
            sessao = Sessao(usuario, container, con)
            con.limpar()
            con.cabecalho("SGME · Gestão de Manutenção", f"Bem-vindo(a), {usuario.nome}")
            painel(sessao)
            con.pausar()
            if Menu(sessao).executar() == "sair":
                break
    except (KeyboardInterrupt, FimDaEntrada):
        con.escrever()
    con.escrever(con.pintar("Até logo!", Cor.CINZA))
