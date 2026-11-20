"""Especialidades: zero, uma ou várias para usuários e OS, e bloqueio de
ordens de serviço incompatíveis com o técnico."""
import pytest

from sgme.domain.entidades import Equipamento, FiltroOS, OrdemServico, Perfil, Usuario
from sgme.domain.especialidades import Especialidade as E, compativel, normalizar
from sgme.domain.excecoes import AcessoNegado, DadosInvalidos, EspecialidadeIncompativel
from sgme.domain.status_os import StatusOS


# ------------------------------------------------------------------ domínio
@pytest.mark.parametrize("exigidas, do_tecnico, esperado", [
    (set(), set(), True),                                   # OS livre, técnico sem especialidade
    (set(), {E.ELETRICA}, True),                            # OS livre aceita qualquer técnico
    ({E.ELETRICA}, set(), False),                           # técnico sem especialidade
    ({E.ELETRICA}, {E.ELETRICA, E.MECANICA}, True),         # técnico com mais do que o exigido
    ({E.ELETRICA, E.HIDRAULICA}, {E.ELETRICA}, False),      # precisa de TODAS
    ({E.ELETRICA, E.HIDRAULICA}, {E.HIDRAULICA, E.ELETRICA}, True),
])
def test_regra_de_compatibilidade(exigidas, do_tecnico, esperado):
    assert compativel(frozenset(exigidas), frozenset(do_tecnico)) is esperado


def test_normaliza_texto_sem_acento_e_duplicados():
    assert normalizar(["eletrica", "ELÉTRICA", "Hidráulica"]) == {E.ELETRICA, E.HIDRAULICA}
    assert normalizar(None) == frozenset()


def test_especialidade_inexistente():
    with pytest.raises(DadosInvalidos):
        Usuario("Ana", Perfil.TECNICO, especialidades=["Astrologia"])


def test_usuario_e_os_aceitam_nenhuma_ou_varias():
    assert Usuario("Ana", Perfil.TECNICO).especialidades == frozenset()
    u = Usuario("Bia", Perfil.TECNICO, especialidades=[E.MECANICA, E.ELETRICA, E.AUTOMACAO])
    assert len(u.especialidades) == 3
    o = OrdemServico(1, 1, "Falha", "Alta", especialidades=["Pneumática", "Mecânica"])
    assert o.especialidades == {E.PNEUMATICA, E.MECANICA}


def test_entidade_bloqueia_atribuicao_incompativel():
    o = OrdemServico(1, 1, "Falha", "Alta", id=1, especialidades=[E.REFRIGERACAO])
    with pytest.raises(EspecialidadeIncompativel, match="Refrigeração"):
        o.atribuir(Usuario("Tec", Perfil.TECNICO, id=9, especialidades=[E.ELETRICA]))
    assert o.status is StatusOS.ABERTA and o.tecnico_id is None


# ----------------------------------------------------------------- serviços
@pytest.fixture
def equipe(container):
    r = container.repositorios
    return {
        "gestor": r.usuarios.adicionar(Usuario("Gestora", Perfil.GESTOR)),
        "eletricista": r.usuarios.adicionar(
            Usuario("Eletricista", Perfil.TECNICO, especialidades=[E.ELETRICA])),
        "multi": r.usuarios.adicionar(
            Usuario("Multi", Perfil.TECNICO, especialidades=[E.ELETRICA, E.HIDRAULICA, E.MECANICA])),
        "generalista": r.usuarios.adicionar(Usuario("Generalista", Perfil.TECNICO)),
        "equip": r.equipamentos.adicionar(Equipamento("Prensa")),
    }


def abrir(container, eq, especialidades=()):
    return container.ordens.abrir(eq["gestor"], eq["equip"].id, "Falha", "Alta", especialidades)


def test_persistencia_das_especialidades(container, equipe):
    os_ = abrir(container, equipe, [E.ELETRICA, E.HIDRAULICA])
    assert container.repositorios.ordens.obter(os_.id).especialidades == {E.ELETRICA, E.HIDRAULICA}
    assert container.usuarios.obter(equipe["multi"].id).especialidades == {
        E.ELETRICA, E.HIDRAULICA, E.MECANICA}
    assert container.usuarios.obter(equipe["generalista"].id).especialidades == frozenset()


def test_bloqueia_tecnico_sem_especialidade(container, equipe):
    os_ = abrir(container, equipe, [E.ELETRICA])
    with pytest.raises(EspecialidadeIncompativel):
        container.ordens.atribuir(equipe["gestor"], os_.id, equipe["generalista"].id)
    salvo = container.repositorios.ordens.obter(os_.id)
    assert salvo.status is StatusOS.ABERTA and salvo.tecnico_id is None
    assert len(container.ordens.detalhar(os_.id).historico) == 1  # nada registrado


def test_bloqueia_quando_falta_uma_de_varias(container, equipe):
    os_ = abrir(container, equipe, [E.ELETRICA, E.HIDRAULICA])
    with pytest.raises(EspecialidadeIncompativel, match="Hidráulica"):
        container.ordens.atribuir(equipe["gestor"], os_.id, equipe["eletricista"].id)
    container.ordens.atribuir(equipe["gestor"], os_.id, equipe["multi"].id)


def test_os_sem_especialidade_aceita_qualquer_tecnico(container, equipe):
    for tecnico in ("eletricista", "multi", "generalista"):
        os_ = abrir(container, equipe)
        container.ordens.atribuir(equipe["gestor"], os_.id, equipe[tecnico].id)


def test_tecnicos_para_indica_o_que_falta(container, equipe):
    os_ = abrir(container, equipe, [E.ELETRICA, E.HIDRAULICA])
    faltas = {t.nome: f for t, f in container.ordens.tecnicos_para(os_.id)}
    assert faltas == {
        "Eletricista": {E.HIDRAULICA},
        "Multi": frozenset(),
        "Generalista": {E.ELETRICA, E.HIDRAULICA},
    }


def test_alterar_especialidades_da_os(container, equipe):
    os_ = abrir(container, equipe)
    container.ordens.definir_especialidades(equipe["gestor"], os_.id, [E.MECANICA, E.ELETRICA])
    assert container.repositorios.ordens.obter(os_.id).especialidades == {E.MECANICA, E.ELETRICA}
    container.ordens.definir_especialidades(equipe["gestor"], os_.id, [])
    assert container.repositorios.ordens.obter(os_.id).especialidades == frozenset()
    assert "Especialidades exigidas alteradas" in container.ordens.detalhar(os_.id).historico[-1].descricao


def test_nao_exige_da_os_o_que_o_tecnico_atribuido_nao_tem(container, equipe):
    os_ = abrir(container, equipe, [E.ELETRICA])
    container.ordens.atribuir(equipe["gestor"], os_.id, equipe["eletricista"].id)
    with pytest.raises(EspecialidadeIncompativel):
        container.ordens.definir_especialidades(equipe["gestor"], os_.id, [E.ELETRICA, E.HIDRAULICA])
    assert container.repositorios.ordens.obter(os_.id).especialidades == {E.ELETRICA}


def test_nao_remove_especialidade_de_tecnico_com_os_ativa(container, equipe):
    os_ = abrir(container, equipe, [E.HIDRAULICA])
    container.ordens.atribuir(equipe["gestor"], os_.id, equipe["multi"].id)
    with pytest.raises(EspecialidadeIncompativel, match=f"OS #{os_.id}"):
        container.usuarios.definir_especialidades(equipe["gestor"], equipe["multi"].id, [E.ELETRICA])
    # remover uma especialidade que a OS não usa é permitido
    container.usuarios.definir_especialidades(equipe["gestor"], equipe["multi"].id, [E.HIDRAULICA])
    # após encerrar a OS, pode ficar sem nenhuma
    container.ordens.encerrar(equipe["gestor"], os_.id, False, "cancelada")
    u = container.usuarios.definir_especialidades(equipe["gestor"], equipe["multi"].id, [])
    assert u.especialidades == frozenset()


def test_somente_gestor_altera_especialidades(container, equipe):
    os_ = abrir(container, equipe)
    with pytest.raises(AcessoNegado):
        container.ordens.definir_especialidades(equipe["eletricista"], os_.id, [E.ELETRICA])
    with pytest.raises(AcessoNegado):
        container.usuarios.definir_especialidades(equipe["eletricista"], equipe["eletricista"].id, [])


def test_cadastro_de_usuario_com_especialidades(container, equipe):
    u = container.usuarios.cadastrar(equipe["gestor"], "Novo", "Técnico", ["Automação", "Pneumática"])
    assert container.usuarios.obter(u.id).especialidades == {E.AUTOMACAO, E.PNEUMATICA}


def test_filtro_por_especialidade(container, equipe):
    abrir(container, equipe, [E.ELETRICA])
    abrir(container, equipe, [E.ELETRICA, E.MECANICA])
    abrir(container, equipe)
    assert len(container.ordens.listar(FiltroOS(especialidade=E.ELETRICA))) == 2
    assert len(container.ordens.listar(FiltroOS(especialidade=E.MECANICA))) == 1
    assert len(container.ordens.listar(FiltroOS(especialidade=E.AUTOMACAO))) == 0
