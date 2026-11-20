from datetime import timedelta

import pytest

from sgme.domain.entidades import FiltroOS, StatusTecnico
from sgme.domain.excecoes import AcessoNegado, DadosInvalidos, NaoEncontrado, TransicaoInvalida
from sgme.domain.status_os import StatusOS
from sgme.services.eventos import EventoOS, ObservadorOS


def abrir(container, dados, crit="Alta"):
    return container.ordens.abrir(dados["gestor"], dados["torno"].id, "Vazamento", crit)


def status_tecnico(container, tecnico):
    return container.usuarios.obter(tecnico.id).status


class TestFluxoCompleto:
    def test_ciclo_de_vida_e_historico(self, container, dados):
        g, joao = dados["gestor"], dados["joao"]
        os_ = abrir(container, dados)
        container.ordens.atribuir(g, os_.id, joao.id)
        container.ordens.registrar_diagnostico(joao, os_.id, "Retentor danificado")
        container.ordens.apontar_reparo(joao, os_.id, 2, "Retentor 40mm")
        container.ordens.alterar_status(joao, os_.id, StatusOS.REPARO_FINALIZADO)
        final = container.ordens.encerrar(g, os_.id, True, "Aprovado")

        assert final.status is StatusOS.CONCLUIDA
        historico = container.ordens.detalhar(os_.id).historico
        assert len(historico) == 6
        assert "aberta" in historico[0].descricao.lower()
        assert "Concluída" in historico[-1].descricao

    def test_persistencia_mantem_dados(self, container, dados):
        os_ = abrir(container, dados, "Baixa")
        salvo = container.repositorios.ordens.obter(os_.id)
        assert salvo.criticidade.value == "Baixa"
        assert salvo.data_abertura == os_.data_abertura


class TestDisponibilidadeTecnico:
    """Corrige bug da Entrega 1: o técnico era liberado ao encerrar uma OS
    mesmo tendo outras OS em andamento."""

    def test_tecnico_fica_em_atendimento_ao_receber_os(self, container, dados):
        os_ = abrir(container, dados)
        container.ordens.atribuir(dados["gestor"], os_.id, dados["joao"].id)
        assert status_tecnico(container, dados["joao"]) is StatusTecnico.EM_ATENDIMENTO

    def test_so_libera_quando_nao_ha_outras_os_ativas(self, container, dados):
        g, joao = dados["gestor"], dados["joao"]
        a, b = abrir(container, dados), abrir(container, dados)
        container.ordens.atribuir(g, a.id, joao.id)
        container.ordens.atribuir(g, b.id, joao.id)

        container.ordens.encerrar(g, a.id, False, "Duplicada")
        assert status_tecnico(container, joao) is StatusTecnico.EM_ATENDIMENTO

        container.ordens.encerrar(g, b.id, False, "Sem necessidade")
        assert status_tecnico(container, joao) is StatusTecnico.DISPONIVEL

    def test_reatribuicao_libera_tecnico_anterior(self, container, dados):
        g = dados["gestor"]
        os_ = abrir(container, dados)
        container.ordens.atribuir(g, os_.id, dados["joao"].id)
        container.ordens.atribuir(g, os_.id, dados["maria"].id)
        assert status_tecnico(container, dados["joao"]) is StatusTecnico.DISPONIVEL
        assert status_tecnico(container, dados["maria"]) is StatusTecnico.EM_ATENDIMENTO


class TestPermissoes:
    def test_tecnico_nao_atribui(self, container, dados):
        os_ = abrir(container, dados)
        with pytest.raises(AcessoNegado):
            container.ordens.atribuir(dados["joao"], os_.id, dados["joao"].id)

    def test_tecnico_nao_encerra(self, container, dados):
        os_ = abrir(container, dados)
        with pytest.raises(AcessoNegado):
            container.ordens.encerrar(dados["joao"], os_.id, False, "x")

    def test_gestor_nao_registra_diagnostico(self, container, dados):
        os_ = abrir(container, dados)
        with pytest.raises(AcessoNegado):
            container.ordens.registrar_diagnostico(dados["gestor"], os_.id, "x")

    def test_tecnico_nao_cadastra_equipamento(self, container, dados):
        with pytest.raises(AcessoNegado):
            container.equipamentos.cadastrar(dados["joao"], "Prensa", "")

    def test_tecnico_nao_mexe_em_os_de_outro(self, container, dados):
        os_ = abrir(container, dados)
        container.ordens.atribuir(dados["gestor"], os_.id, dados["joao"].id)
        with pytest.raises(TransicaoInvalida):
            container.ordens.apontar_reparo(dados["maria"], os_.id, 1, "")


class TestValidacoesDeServico:
    def test_os_inexistente(self, container, dados):
        with pytest.raises(NaoEncontrado):
            container.ordens.detalhar(999)

    def test_equipamento_inexistente(self, container, dados):
        with pytest.raises(NaoEncontrado):
            container.ordens.abrir(dados["gestor"], 999, "x", "Alta")

    def test_atribuir_a_gestor_e_invalido(self, container, dados):
        os_ = abrir(container, dados)
        with pytest.raises(DadosInvalidos):
            container.ordens.atribuir(dados["gestor"], os_.id, dados["gestor"].id)

    def test_equipamento_inativo_nao_recebe_os(self, container, dados):
        container.equipamentos.alternar_ativo(dados["gestor"], dados["torno"].id)
        with pytest.raises(DadosInvalidos):
            abrir(container, dados)

    def test_nao_inativa_equipamento_com_os_ativa(self, container, dados):
        abrir(container, dados)
        with pytest.raises(TransicaoInvalida):
            container.equipamentos.alternar_ativo(dados["gestor"], dados["torno"].id)

    def test_tecnico_so_define_status_operacional(self, container, dados):
        os_ = abrir(container, dados)
        container.ordens.atribuir(dados["gestor"], os_.id, dados["joao"].id)
        with pytest.raises(DadosInvalidos):
            container.ordens.alterar_status(dados["joao"], os_.id, StatusOS.CONCLUIDA)


class TestConsultasEPainel:
    def test_fila_prioriza_atrasadas_e_criticidade(self, container, dados, relogio):
        baixa = abrir(container, dados, "Baixa")
        alta = abrir(container, dados, "Alta")
        media = abrir(container, dados, "Média")
        relogio.agora += timedelta(hours=30)  # média (24h) e alta (4h) atrasadas; baixa (72h) não
        fila = [r.ordem.id for r in container.ordens.fila_priorizada()]
        assert fila == [alta.id, media.id, baixa.id]

    def test_filtros(self, container, dados):
        abrir(container, dados, "Baixa")
        abrir(container, dados, "Alta")
        assert len(container.ordens.listar(FiltroOS(texto="vaza"))) == 2
        from sgme.domain.sla import Criticidade
        assert len(container.ordens.listar(FiltroOS(criticidade=Criticidade.ALTA))) == 1

    def test_painel(self, container, dados, relogio):
        abrir(container, dados, "Alta")
        relogio.agora += timedelta(hours=5)
        p = container.painel.gerar()
        assert p.ativas == 1 and len(p.atrasadas) == 1 and p.total == 1


class TestObserverExtensivel:
    def test_novo_observador_sem_alterar_servico(self, container, dados):
        recebidos = []

        class Auditoria(ObservadorOS):
            def notificar(self, evento: EventoOS) -> None:
                recebidos.append(evento.tipo)

        container.ordens._eventos.inscrever(Auditoria())
        abrir(container, dados)
        assert [t.value for t in recebidos] == ["aberta"]
