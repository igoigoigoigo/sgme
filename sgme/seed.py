"""Dados iniciais de demonstração (equivalente ao 'Mock Data' da Entrega 1).

Os dados são criados pelos próprios serviços, então o histórico e o status dos
técnicos já nascem coerentes.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sgme.container import Container, montar
from sgme.domain.entidades import Equipamento, Perfil, Usuario
from sgme.domain.status_os import StatusOS


def popular_se_vazio(container: Container) -> bool:
    repos = container.repositorios
    if repos.usuarios.listar():
        return False

    gestor = repos.usuarios.adicionar(Usuario("Gestor Admin", Perfil.GESTOR))
    joao = repos.usuarios.adicionar(Usuario("Tecnico Joao", Perfil.TECNICO))
    maria = repos.usuarios.adicionar(Usuario("Tecnica Maria", Perfil.TECNICO))
    repos.usuarios.adicionar(Usuario("Tecnico Carlos", Perfil.TECNICO))

    torno = repos.equipamentos.adicionar(
        Equipamento("Torno Mecânico CNC", "Equipamento de usinagem setor A"))
    compressor = repos.equipamentos.adicionar(
        Equipamento("Compressor de Ar", "Compressor parafuso 20 HP - utilidades"))
    prensa = repos.equipamentos.adicionar(
        Equipamento("Prensa Hidráulica", "Prensa 100 t - estamparia setor B"))
    repos.equipamentos.adicionar(
        Equipamento("Empilhadeira Elétrica", "Empilhadeira 2,5 t - almoxarifado"))

    # Uma OS aberta há 6 horas (com relógio injetado) para demonstrar SLA estourado
    passado = montar(repos, relogio=lambda: datetime.now() - timedelta(hours=6))
    os1 = passado.ordens.abrir(gestor, prensa.id, "Vazamento de óleo no cilindro principal", "Alta")
    passado.ordens.atribuir(gestor, os1.id, joao.id)

    ordens = container.ordens
    os2 = ordens.abrir(joao, compressor.id, "Ruído anormal e aquecimento no cabeçote", "Média")
    ordens.atribuir(gestor, os2.id, maria.id)
    ordens.registrar_diagnostico(maria, os2.id, "Rolamento do motor com desgaste")
    ordens.alterar_status(maria, os2.id, StatusOS.AGUARDANDO_PECA)

    ordens.abrir(gestor, torno.id, "Folga no carro transversal", "Baixa")
    return True



def garantir_gestor(container: Container) -> None:
    """Sem dados de demonstração, cria apenas um gestor para permitir o primeiro acesso."""
    if not container.repositorios.usuarios.listar():
        container.repositorios.usuarios.adicionar(Usuario("Gestor Admin", Perfil.GESTOR))
