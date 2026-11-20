"""Raiz de composição — Injeção de Dependência.

É o ÚNICO lugar que conhece as classes concretas. Aqui se decide se os
repositórios são SQLite ou em memória e quais observadores estão inscritos.
Os serviços recebem tudo pelo construtor e dependem apenas de abstrações
(Princípio da Inversão de Dependência).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sgme.repositories.interfaces import (
    EquipamentoRepository, HistoricoRepository, OrdemServicoRepository, UsuarioRepository,
)
from sgme.repositories.memoria import (
    EquipamentoRepositoryMemoria, HistoricoRepositoryMemoria,
    OrdemServicoRepositoryMemoria, UsuarioRepositoryMemoria,
)
from sgme.repositories.sqlite import (
    Database, EquipamentoRepositorySQLite, HistoricoRepositorySQLite,
    OrdemServicoRepositorySQLite, UsuarioRepositorySQLite,
)
from sgme.services.cadastros import EquipamentoService, UsuarioService
from sgme.services.eventos import (
    DisponibilidadeTecnicoObserver, PublicadorEventos, RegistroHistoricoObserver,
)
from sgme.services.ordem_servico import OrdemServicoService
from sgme.services.painel import PainelService


@dataclass
class Repositorios:
    usuarios: UsuarioRepository
    equipamentos: EquipamentoRepository
    ordens: OrdemServicoRepository
    historico: HistoricoRepository


@dataclass
class Container:
    repositorios: Repositorios
    usuarios: UsuarioService
    equipamentos: EquipamentoService
    ordens: OrdemServicoService
    painel: PainelService


def repositorios_sqlite(caminho_db: str) -> Repositorios:
    db = Database(caminho_db)
    db.inicializar()
    return Repositorios(
        usuarios=UsuarioRepositorySQLite(db),
        equipamentos=EquipamentoRepositorySQLite(db),
        ordens=OrdemServicoRepositorySQLite(db),
        historico=HistoricoRepositorySQLite(db),
    )


def repositorios_memoria() -> Repositorios:
    return Repositorios(
        usuarios=UsuarioRepositoryMemoria(),
        equipamentos=EquipamentoRepositoryMemoria(),
        ordens=OrdemServicoRepositoryMemoria(),
        historico=HistoricoRepositoryMemoria(),
    )


def montar(repos: Repositorios, relogio: Callable[[], datetime] = datetime.now) -> Container:
    eventos = PublicadorEventos()
    eventos.inscrever(RegistroHistoricoObserver(repos.historico))
    eventos.inscrever(DisponibilidadeTecnicoObserver(repos.usuarios, repos.ordens))

    usuarios = UsuarioService(repos.usuarios, repos.ordens)
    equipamentos = EquipamentoService(repos.equipamentos, repos.ordens)
    ordens = OrdemServicoService(
        repos.ordens, repos.equipamentos, repos.usuarios, repos.historico, eventos, relogio,
    )
    return Container(
        repositorios=repos,
        usuarios=usuarios,
        equipamentos=equipamentos,
        ordens=ordens,
        painel=PainelService(ordens, usuarios),
    )
