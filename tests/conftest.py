import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sgme.container import montar, repositorios_memoria, repositorios_sqlite  # noqa: E402
from sgme.domain.entidades import Equipamento, Perfil, Usuario  # noqa: E402


class RelogioFalso:
    def __init__(self, inicio: datetime = datetime(2026, 1, 10, 8, 0, 0)) -> None:
        self.agora = inicio

    def __call__(self) -> datetime:
        return self.agora


@pytest.fixture
def relogio():
    return RelogioFalso()


@pytest.fixture(params=["memoria", "sqlite"])
def container(request, tmp_path, relogio):
    """Os mesmos testes rodam com as duas implementações de repositório
    (verificação prática do Princípio de Substituição de Liskov)."""
    repos = (repositorios_memoria() if request.param == "memoria"
             else repositorios_sqlite(str(tmp_path / "teste.db")))
    return montar(repos, relogio)


@pytest.fixture
def dados(container):
    r = container.repositorios
    gestor = r.usuarios.adicionar(Usuario("Gestora Ana", Perfil.GESTOR))
    joao = r.usuarios.adicionar(Usuario("Tecnico Joao", Perfil.TECNICO))
    maria = r.usuarios.adicionar(Usuario("Tecnica Maria", Perfil.TECNICO))
    torno = r.equipamentos.adicionar(Equipamento("Torno CNC", "Setor A"))
    return {"gestor": gestor, "joao": joao, "maria": maria, "torno": torno}
