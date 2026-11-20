"""Ponto de entrada do SGME.

Uso:
    python main.py                    # usa o banco manutencao.db (cria se não existir)
    python main.py --db outro.db      # usa outro arquivo de banco
    python main.py --memoria          # executa sem gravar em disco (demonstração)
"""
from __future__ import annotations

import argparse
import sys

from sgme.cli.app import executar
from sgme.container import montar, repositorios_memoria, repositorios_sqlite
from sgme.seed import garantir_gestor, popular_se_vazio


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="SGME - Gestão de Manutenção de Equipamentos")
    parser.add_argument("--db", default="manutencao.db", help="arquivo SQLite (padrão: manutencao.db)")
    parser.add_argument("--memoria", action="store_true", help="usa repositórios em memória")
    parser.add_argument("--sem-demo", action="store_true", help="não cria dados de demonstração")
    args = parser.parse_args(argv)

    repos = repositorios_memoria() if args.memoria else repositorios_sqlite(args.db)
    container = montar(repos)
    if args.sem_demo:
        garantir_gestor(container)
    else:
        popular_se_vazio(container)
    executar(container)


if __name__ == "__main__":
    main()
