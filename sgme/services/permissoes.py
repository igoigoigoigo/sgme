"""Controle de acesso por perfil — padrão Factory Method.

Na Entrega 1, a permissão estava implícita em qual menu era exibido: as
funções em si não verificavam nada (um técnico poderia chamar
`encerramento_administrativo` se ela estivesse no menu dele).

Agora cada perfil tem uma política de acesso, criada por uma fábrica a partir
do perfil do usuário. Os serviços pedem a política e verificam a ação; a CLI
usa a mesma política para montar o menu. Um novo perfil (ex.: "Operador")
exige apenas uma nova classe registrada na fábrica.
"""
from __future__ import annotations

from abc import ABC
from enum import Enum

from sgme.domain.entidades import Perfil, Usuario
from sgme.domain.excecoes import AcessoNegado


class Acao(str, Enum):
    ABRIR_OS = "abrir_os"
    ATRIBUIR_OS = "atribuir_os"
    ENCERRAR_OS = "encerrar_os"
    TRABALHAR_OS = "trabalhar_os"            # diagnóstico, apontamento, status
    GERENCIAR_EQUIPAMENTOS = "gerenciar_equipamentos"
    GERENCIAR_USUARIOS = "gerenciar_usuarios"


class PoliticaAcesso(ABC):
    acoes: frozenset[Acao] = frozenset()

    def pode(self, acao: Acao) -> bool:
        return acao in self.acoes

    def exigir(self, acao: Acao) -> None:
        if not self.pode(acao):
            raise AcessoNegado("Seu perfil não tem permissão para esta operação.")


class PoliticaGestor(PoliticaAcesso):
    acoes = frozenset({
        Acao.ABRIR_OS, Acao.ATRIBUIR_OS, Acao.ENCERRAR_OS,
        Acao.GERENCIAR_EQUIPAMENTOS, Acao.GERENCIAR_USUARIOS,
    })


class PoliticaTecnico(PoliticaAcesso):
    acoes = frozenset({Acao.ABRIR_OS, Acao.TRABALHAR_OS})


class FabricaPoliticaAcesso:
    _registro: dict[Perfil, type[PoliticaAcesso]] = {
        Perfil.GESTOR: PoliticaGestor,
        Perfil.TECNICO: PoliticaTecnico,
    }

    @classmethod
    def registrar(cls, perfil: Perfil, politica: type[PoliticaAcesso]) -> None:
        cls._registro[perfil] = politica

    @classmethod
    def criar(cls, usuario: Usuario) -> PoliticaAcesso:
        try:
            return cls._registro[usuario.perfil]()
        except KeyError as exc:
            raise AcessoNegado(f"Perfil sem política de acesso: {usuario.perfil}") from exc
