"""Componentes de entrada e saída do terminal.

Concentra cores, tabelas e leitura validada de dados. Na Entrega 1, cada
função fazia seu próprio `input()` sem validação (um ID com letra derrubava o
programa com `ValueError`). Aqui toda leitura passa por métodos que repetem a
pergunta até receber um valor válido ou o usuário cancelar.

As funções de entrada/saída são injetadas, o que permite testar as telas com
respostas roteirizadas.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")


class Cancelado(Exception):
    """Usuário desistiu da operação (Enter vazio)."""


class FimDaEntrada(Exception):
    """A entrada padrão terminou (Ctrl+Z/Ctrl+D ou fim de um roteiro): encerra o programa."""


class Cor:
    RESET = "\033[0m"
    NEGRITO = "\033[1m"
    FRACO = "\033[2m"
    VERMELHO = "\033[31m"
    VERDE = "\033[32m"
    AMARELO = "\033[33m"
    AZUL = "\033[34m"
    MAGENTA = "\033[35m"
    CIANO = "\033[36m"
    CINZA = "\033[90m"


def _habilitar_ansi() -> bool:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        os.system("")  # ativa sequências ANSI no console do Windows
    return True


@dataclass(frozen=True)
class Coluna:
    titulo: str
    minimo: int = 4
    flex: bool = False      # coluna que encolhe/expande conforme a largura do terminal
    direita: bool = False


# Uma célula pode ser texto simples ou (texto, cor)
Celula = str | tuple[str, str]


class Console:
    def __init__(
        self,
        entrada: Callable[[str], str] = input,
        saida: Callable[[str], None] = print,
        cores: bool | None = None,
        largura: int | None = None,
    ) -> None:
        self._entrada = entrada
        self._saida = saida
        self.cores = _habilitar_ansi() if cores is None else cores
        self._largura_fixa = largura

    # ------------------------------------------------------------------ saída
    @property
    def largura(self) -> int:
        if self._largura_fixa:
            return self._largura_fixa
        return max(60, min(shutil.get_terminal_size((100, 30)).columns, 140))

    def pintar(self, texto: str, *cores: str) -> str:
        if not self.cores or not cores:
            return texto
        return "".join(cores) + texto + Cor.RESET

    def escrever(self, texto: str = "") -> None:
        self._saida(texto)

    def limpar(self) -> None:
        if self.cores and self._largura_fixa is None:
            self._saida("\033[2J\033[H")

    def cabecalho(self, titulo: str, subtitulo: str = "") -> None:
        linha = "═" * self.largura
        self.escrever(self.pintar(linha, Cor.AZUL))
        self.escrever(self.pintar(f" {titulo}", Cor.NEGRITO, Cor.CIANO)
                      + (self.pintar(f"  {subtitulo}", Cor.CINZA) if subtitulo else ""))
        self.escrever(self.pintar(linha, Cor.AZUL))

    def secao(self, titulo: str) -> None:
        self.escrever()
        resto = max(0, self.largura - len(titulo) - 4)
        self.escrever(self.pintar(f"── {titulo} ", Cor.NEGRITO) + self.pintar("─" * resto, Cor.CINZA))

    def sucesso(self, msg: str) -> None:
        self.escrever(self.pintar(f"✔ {msg}", Cor.VERDE))

    def erro(self, msg: str) -> None:
        self.escrever(self.pintar(f"✖ {msg}", Cor.VERMELHO))

    def aviso(self, msg: str) -> None:
        self.escrever(self.pintar(f"! {msg}", Cor.AMARELO))

    def info(self, msg: str) -> None:
        self.escrever(self.pintar(msg, Cor.CINZA))

    def campo(self, rotulo: str, valor: str | None, cor: str = "") -> None:
        valor = valor if valor not in (None, "") else self.pintar("—", Cor.CINZA)
        self.escrever(f"  {self.pintar(rotulo.ljust(16), Cor.CINZA)} {self.pintar(str(valor), cor) if cor else valor}")

    def tabela(self, colunas: Sequence[Coluna], linhas: Iterable[Sequence[Celula]],
               vazio: str = "Nenhum registro encontrado.") -> None:
        linhas = [list(l) for l in linhas]
        if not linhas:
            self.info(f"  {vazio}")
            return
        textos = [[c if isinstance(c, str) else c[0] for c in l] for l in linhas]
        larguras = [
            max([len(col.titulo), col.minimo] + [len(l[i]) for l in textos])
            for i, col in enumerate(colunas)
        ]
        # "Responsividade" no terminal: ajusta colunas flexíveis à largura disponível
        separador = 3
        excesso = sum(larguras) + separador * (len(colunas) - 1) + 2 - self.largura
        flex = [i for i, c in enumerate(colunas) if c.flex]
        while excesso > 0 and flex:
            i = max(flex, key=lambda k: larguras[k])
            if larguras[i] <= colunas[i].minimo:
                flex.remove(i)
                continue
            larguras[i] -= 1
            excesso -= 1

        def formatar(texto: str, i: int) -> str:
            if len(texto) > larguras[i]:
                texto = texto[: larguras[i] - 1] + "…"
            return texto.rjust(larguras[i]) if colunas[i].direita else texto.ljust(larguras[i])

        sep = self.pintar(" │ ", Cor.CINZA)
        self.escrever("  " + sep.join(
            self.pintar(formatar(c.titulo, i), Cor.NEGRITO) for i, c in enumerate(colunas)))
        self.escrever("  " + self.pintar("─┼─".join("─" * w for w in larguras), Cor.CINZA))
        for linha in linhas:
            celulas = []
            for i, c in enumerate(linha):
                texto, cor = (c, "") if isinstance(c, str) else c
                celulas.append(self.pintar(formatar(texto, i), cor) if cor else formatar(texto, i))
            self.escrever("  " + sep.join(celulas))

    # ---------------------------------------------------------------- entrada
    def _ler(self, prompt: str) -> str:
        try:
            return self._entrada(self.pintar(f"  {prompt} ", Cor.AMARELO) + self.pintar("› ", Cor.CINZA)).strip()
        except EOFError as exc:
            raise FimDaEntrada() from exc

    def texto(self, prompt: str, obrigatorio: bool = True, padrao: str | None = None) -> str:
        dica = f" [{padrao}]" if padrao else ""
        valor = self._ler(f"{prompt}{dica}")
        if not valor:
            if padrao is not None:
                return padrao
            if obrigatorio:
                raise Cancelado()
        return valor

    def inteiro(self, prompt: str, validos: Iterable[int] | None = None) -> int:
        validos = set(validos) if validos is not None else None
        while True:
            valor = self._ler(prompt)
            if not valor:
                raise Cancelado()
            if not valor.lstrip("#").isdigit():
                self.erro("Digite apenas números.")
                continue
            numero = int(valor.lstrip("#"))
            if validos is not None and numero not in validos:
                self.erro("Opção não disponível na lista acima.")
                continue
            return numero

    def decimal(self, prompt: str) -> float:
        while True:
            valor = self._ler(prompt)
            if not valor:
                raise Cancelado()
            try:
                return float(valor.replace(",", "."))
            except ValueError:
                self.erro("Valor numérico inválido (ex.: 2,5).")

    def escolher(self, prompt: str, opcoes: Sequence[tuple[str, T]]) -> T:
        """Exibe opções numeradas e devolve o valor associado à escolhida."""
        for i, (rotulo, _) in enumerate(opcoes, start=1):
            self.escrever(f"    {self.pintar(str(i).rjust(2), Cor.CIANO)}  {rotulo}")
        indice = self.inteiro(prompt, range(1, len(opcoes) + 1))
        return opcoes[indice - 1][1]

    def confirmar(self, prompt: str) -> bool:
        while True:
            valor = self._ler(f"{prompt} (s/n)").lower()
            if valor in ("s", "sim", "y"):
                return True
            if valor in ("n", "nao", "não", ""):
                return False
            self.erro("Responda com 's' ou 'n'.")

    def pausar(self) -> None:
        try:
            self._entrada(self.pintar("\n  Pressione Enter para continuar…", Cor.CINZA))
        except EOFError as exc:
            raise FimDaEntrada() from exc
