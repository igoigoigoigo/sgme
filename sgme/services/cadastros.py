"""Serviços de cadastro: usuários e equipamentos."""
from __future__ import annotations

from typing import Iterable

from sgme.domain.entidades import Equipamento, FiltroOS, Perfil, Usuario
from sgme.domain.especialidades import Especialidade, faltantes, normalizar, rotulo
from sgme.domain.excecoes import (
    DadosInvalidos, EspecialidadeIncompativel, NaoEncontrado, TransicaoInvalida,
)
from sgme.repositories.interfaces import (
    EquipamentoRepository, OrdemServicoRepository, UsuarioRepository,
)
from .permissoes import Acao, FabricaPoliticaAcesso


class UsuarioService:
    def __init__(self, usuarios: UsuarioRepository, ordens: OrdemServicoRepository) -> None:
        self._usuarios = usuarios
        self._ordens = ordens

    def listar(self) -> list[Usuario]:
        return self._usuarios.listar()

    def listar_tecnicos(self) -> list[Usuario]:
        return self._usuarios.listar(Perfil.TECNICO)

    def obter(self, usuario_id: int) -> Usuario:
        usuario = self._usuarios.obter(usuario_id)
        if usuario is None:
            raise NaoEncontrado(f"Usuário #{usuario_id} não encontrado.")
        return usuario

    def cadastrar(self, ator: Usuario, nome: str, perfil: str,
                  especialidades: Iterable[Especialidade | str] = ()) -> Usuario:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.GERENCIAR_USUARIOS)
        try:
            perfil_enum = Perfil(perfil)
        except ValueError as exc:
            raise DadosInvalidos(f"Perfil inválido: {perfil!r}") from exc
        return self._usuarios.adicionar(
            Usuario(nome=nome, perfil=perfil_enum, especialidades=especialidades)
        )

    def definir_especialidades(self, ator: Usuario, usuario_id: int,
                               especialidades: Iterable[Especialidade | str]) -> Usuario:
        """Altera as especialidades do usuário. Bloqueado se ele tiver OS ativa
        que exija uma especialidade que estaria sendo removida."""
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.GERENCIAR_USUARIOS)
        usuario = self.obter(usuario_id)
        novas = normalizar(especialidades)
        conflitos = [
            (o.id, faltantes(o.especialidades, novas))
            for o in self._ordens.listar(FiltroOS(tecnico_id=usuario_id, apenas_ativas=True))
            if faltantes(o.especialidades, novas)
        ]
        if conflitos:
            detalhes = "; ".join(f"OS #{i} exige {rotulo(f)}" for i, f in conflitos)
            raise EspecialidadeIncompativel(
                f"{usuario.nome} possui OS ativas que dependem dessas especialidades ({detalhes}). "
                "Reatribua as OS antes de removê-las."
            )
        usuario.especialidades = novas
        self._usuarios.atualizar(usuario)
        return usuario


class EquipamentoService:
    def __init__(self, equipamentos: EquipamentoRepository,
                 ordens: OrdemServicoRepository) -> None:
        self._equipamentos = equipamentos
        self._ordens = ordens

    def listar(self, apenas_ativos: bool = False) -> list[Equipamento]:
        return self._equipamentos.listar(apenas_ativos)

    def obter(self, equipamento_id: int) -> Equipamento:
        equipamento = self._equipamentos.obter(equipamento_id)
        if equipamento is None:
            raise NaoEncontrado(f"Equipamento #{equipamento_id} não encontrado.")
        return equipamento

    def cadastrar(self, ator: Usuario, nome: str, descricao: str) -> Equipamento:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.GERENCIAR_EQUIPAMENTOS)
        return self._equipamentos.adicionar(Equipamento(nome=nome, descricao=descricao))

    def editar(self, ator: Usuario, equipamento_id: int, nome: str, descricao: str) -> Equipamento:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.GERENCIAR_EQUIPAMENTOS)
        atual = self.obter(equipamento_id)
        editado = Equipamento(nome=nome or atual.nome,
                              descricao=descricao if descricao else atual.descricao,
                              ativo=atual.ativo, id=atual.id)
        self._equipamentos.atualizar(editado)
        return editado

    def alternar_ativo(self, ator: Usuario, equipamento_id: int) -> Equipamento:
        FabricaPoliticaAcesso.criar(ator).exigir(Acao.GERENCIAR_EQUIPAMENTOS)
        equipamento = self.obter(equipamento_id)
        if equipamento.ativo and self._ordens.listar(
            FiltroOS(equipamento_id=equipamento_id, apenas_ativas=True)
        ):
            raise TransicaoInvalida(
                "Equipamento possui OS em aberto e não pode ser inativado."
            )
        equipamento.ativo = not equipamento.ativo
        self._equipamentos.atualizar(equipamento)
        return equipamento
