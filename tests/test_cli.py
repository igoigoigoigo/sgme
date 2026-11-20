"""Testes da interface com entradas roteirizadas (Console com E/S injetadas)."""
from sgme.cli.app import executar
from sgme.cli.console import Console
from sgme.container import montar, repositorios_memoria
from sgme.domain.status_os import StatusOS
from sgme.seed import popular_se_vazio


def rodar(respostas):
    fila = list(respostas)
    saida: list[str] = []

    def entrada(prompt: str) -> str:
        saida.append(prompt)
        if not fila:
            raise EOFError
        return fila.pop(0)

    c = montar(repositorios_memoria())
    popular_se_vazio(c)
    executar(c, Console(entrada, saida.append, cores=False, largura=100))
    return c, "\n".join(saida)


def test_gestor_abre_chamado_pelo_menu():
    # login gestor, Enter no painel, opção 5 (abrir), equipamento 1, falha, criticidade 1 (Alta)
    c, texto = rodar(["1", "", "5", "1", "Motor travado", "1", "", "", "0"])
    assert "Chamado aberto: OS #4 (Alta; especialidades: nenhuma)" in texto
    assert c.ordens.detalhar(4).resumo.ordem.falha_apontada == "Motor travado"


def test_entrada_invalida_nao_derruba_o_programa():
    _, texto = rodar(["1", "", "abc", "", "4", "xyz", "999", "", "0"])
    assert "Opção inválida" in texto
    assert "Digite apenas números" in texto
    assert "OS #999 não encontrada" in texto


def test_menu_do_tecnico_nao_mostra_opcoes_de_gestor():
    _, texto = rodar(["2", "", "0"])
    assert "Registrar diagnóstico" in texto
    assert "Atribuir / reatribuir técnico" not in texto
    assert "Cadastrar usuário" not in texto


def test_tecnico_finaliza_reparo():
    # Tecnico Joao (login 2) tem a OS #1; menu: 1 painel, 2 minhas, 3 consultar, 4 detalhes,
    # 5 abrir, 6 diagnóstico, 7 apontar, 8 status
    c, texto = rodar(["2", "", "8", "1", "3", "", "0"])
    assert c.ordens.detalhar(1).resumo.ordem.status is StatusOS.REPARO_FINALIZADO


def test_atribuicao_incompativel_e_bloqueada_na_interface():
    # Gestor › 6 Atribuir › OS #1 (exige Hidráulica) › Tecnico Carlos (#4, sem especialidade)
    c, texto = rodar(["1", "", "6", "1", "4", "", "0"])
    assert "✖ falta Hidráulica" in texto
    assert "Tecnico Carlos não possui a(s) especialidade(s) exigida(s) pela OS: Hidráulica" in texto
    assert c.ordens.detalhar(1).resumo.tecnico == "Tecnico Joao"


def test_abre_chamado_com_varias_especialidades():
    c, texto = rodar(["1", "", "5", "1", "Curto no painel", "1", "2,7", "", "0"])
    assert "especialidades: Elétrica, Automação" in texto
