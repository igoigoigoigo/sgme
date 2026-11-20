"""Exceções de domínio.

A camada de apresentação traduz essas exceções em mensagens para o usuário,
sem que o domínio precise saber se está rodando na Web, no console ou em testes.
"""


class ErroDominio(Exception):
    """Base de todos os erros de regra de negócio."""


class DadosInvalidos(ErroDominio):
    """Entrada do usuário não atende às validações."""


class NaoEncontrado(ErroDominio):
    """Recurso solicitado não existe."""


class AcessoNegado(ErroDominio):
    """O perfil do usuário não permite a operação."""


class TransicaoInvalida(ErroDominio):
    """Mudança de status não permitida pela máquina de estados da OS."""


class EspecialidadeIncompativel(ErroDominio):
    """O técnico não possui as especialidades exigidas pela OS."""
