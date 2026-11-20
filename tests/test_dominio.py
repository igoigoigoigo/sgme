from datetime import datetime, timedelta

import pytest

from sgme.domain.entidades import Equipamento, OrdemServico, Usuario
from sgme.domain.excecoes import DadosInvalidos, TransicaoInvalida
from sgme.domain.sla import Criticidade, politica_sla
from sgme.domain.status_os import StatusOS, estado_de


TEC5 = Usuario("Tecnico Cinco", "Técnico", id=5)


def nova_os(**kw) -> OrdemServico:
    base = dict(equipamento_id=1, criador_id=1, falha_apontada="Ruído", criticidade="Alta", id=1)
    base.update(kw)
    return OrdemServico(**base)


class TestValidacoes:
    def test_nome_obrigatorio(self):
        with pytest.raises(DadosInvalidos):
            Equipamento(nome="   ")

    def test_falha_obrigatoria(self):
        with pytest.raises(DadosInvalidos):
            nova_os(falha_apontada="")

    def test_criticidade_invalida(self):
        with pytest.raises(DadosInvalidos):
            nova_os(criticidade="Urgentíssima")

    @pytest.mark.parametrize("texto", ["Media", "media", "MÉDIA", "Média"])
    def test_criticidade_aceita_formato_da_entrega1(self, texto):
        assert nova_os(criticidade=texto).criticidade is Criticidade.MEDIA

    def test_perfil_invalido(self):
        with pytest.raises(ValueError):
            Usuario("Fulano", "Administrador")


class TestMaquinaDeEstados:
    def test_atribuir_move_para_em_andamento(self):
        o = nova_os()
        o.atribuir(TEC5)
        assert o.status is StatusOS.EM_ANDAMENTO and o.tecnico_id == 5

    def test_nao_pode_concluir_sem_reparo_finalizado(self):
        o = nova_os()
        o.atribuir(TEC5)
        with pytest.raises(TransicaoInvalida):
            o.encerrar(True, "ok", datetime.now())

    def test_pode_cancelar_os_aberta(self):
        o = nova_os()
        o.encerrar(False, "duplicada", datetime.now())
        assert o.status is StatusOS.CANCELADA and o.data_encerramento

    def test_os_finalizada_nao_aceita_mais_nada(self):
        o = nova_os()
        o.encerrar(False, "duplicada", datetime.now())
        with pytest.raises(TransicaoInvalida):
            o.atribuir(TEC5)
        assert estado_de(o.status).transicoes == frozenset()

    def test_apenas_tecnico_atribuido_trabalha(self):
        o = nova_os()
        o.atribuir(TEC5)
        with pytest.raises(TransicaoInvalida):
            o.registrar_diagnostico(6, "x")

    def test_diagnostico_exige_os_atribuida(self):
        with pytest.raises(TransicaoInvalida):
            nova_os().registrar_diagnostico(None, "x")

    def test_apontamento_acumula_horas_e_pecas(self):
        o = nova_os()
        o.atribuir(TEC5)
        o.apontar_reparo(5, "1,5", "Rolamento")
        o.apontar_reparo(5, 2, "Correia")
        assert o.horas_trabalhadas == 3.5
        assert o.pecas_utilizadas == "Rolamento; Correia"

    @pytest.mark.parametrize("horas", ["abc", 0, -1, 25])
    def test_apontamento_rejeita_horas_invalidas(self, horas):
        o = nova_os()
        o.atribuir(TEC5)
        with pytest.raises(DadosInvalidos):
            o.apontar_reparo(5, horas, "")

    def test_devolver_para_execucao(self):
        o = nova_os()
        o.atribuir(TEC5)
        o.alterar_status_operacional(5, StatusOS.REPARO_FINALIZADO)
        o.devolver_para_execucao("ainda vaza")
        assert o.status is StatusOS.EM_EXECUCAO


class TestSLA:
    def test_prazos_por_criticidade(self):
        assert politica_sla("Alta").prazo == timedelta(hours=4)
        assert politica_sla(Criticidade.MEDIA).prazo == timedelta(hours=24)
        assert politica_sla("baixa").prazo == timedelta(hours=72)

    def test_atraso(self):
        alta = politica_sla("Alta")
        abertura = datetime(2026, 1, 1, 8, 0)
        assert not alta.esta_atrasada(abertura, abertura + timedelta(hours=3), False)
        assert alta.esta_atrasada(abertura, abertura + timedelta(hours=5), False)
        assert not alta.esta_atrasada(abertura, abertura + timedelta(hours=5), True)

    def test_peso_ordena_por_urgencia(self):
        pesos = [politica_sla(c).peso for c in ("Alta", "Média", "Baixa")]
        assert pesos == sorted(pesos, reverse=True)
