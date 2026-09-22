"""Tipos do domínio do Desafio Fenrir.

Tudo aqui é imutável (`frozen=True`). O estado da competição — caixa, posições,
patrimônio — nunca é guardado: é sempre *derivado* do ledger de trades. Essa é a
decisão de desenho central desta reescrita. Na versão anterior a custódia era
editada no lugar, e um bloco de código duplicado aplicava a mesma ordem duas
vezes sem deixar rastro. Com estado derivado, aplicar uma ordem duas vezes exige
duas linhas no ledger — visíveis a olho nu e detectáveis por teste.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class Moeda(str, Enum):
    BRL = "BRL"
    USD = "USD"


class Direcao(str, Enum):
    COMPRA = "COMPRA"
    VENDA = "VENDA"

    @property
    def sinal(self) -> int:
        """+1 aumenta a posição, -1 reduz (e pode virar short)."""
        return 1 if self is Direcao.COMPRA else -1


@dataclass(frozen=True)
class Ativo:
    ticker: str
    nome: str
    moeda: Moeda

    @property
    def estrangeiro(self) -> bool:
        return self.moeda is not Moeda.BRL


@dataclass(frozen=True)
class Ordem:
    """Boleta enviada por um fundo. Ainda não executada."""

    fundo: str
    ticker: str
    quantidade: int  # sempre positiva; a direção vive em `direcao`
    direcao: Direcao
    enviada_em: datetime

    def __post_init__(self) -> None:
        if self.quantidade <= 0:
            raise ValueError("Quantidade da boleta deve ser positiva.")


@dataclass(frozen=True)
class Trade:
    """Ordem executada. Linha imutável do ledger.

    `quantidade` é **assinada**: positiva para compra, negativa para venda. Com
    isso a posição é a soma das quantidades e o fluxo de caixa é o oposto do
    financeiro — não há `if compra/venda` espalhado pelo motor.
    """

    fundo: str
    ticker: str
    quantidade: int
    preco_nativo: Decimal
    cambio: Decimal  # BRL por unidade da moeda do ativo (1 para ativos em BRL)
    executado_em: date

    def __post_init__(self) -> None:
        if self.quantidade == 0:
            raise ValueError("Trade com quantidade zero não deveria existir.")
        if self.preco_nativo <= 0:
            raise ValueError("Preço de execução deve ser positivo.")
        if self.cambio <= 0:
            raise ValueError("Câmbio deve ser positivo.")

    @property
    def preco_brl(self) -> Decimal:
        return self.preco_nativo * self.cambio

    @property
    def financeiro(self) -> Decimal:
        """Valor absoluto negociado, em reais."""
        return abs(Decimal(self.quantidade)) * self.preco_brl

    @property
    def fluxo_caixa(self) -> Decimal:
        """Compra tira do caixa, venda põe no caixa."""
        return -Decimal(self.quantidade) * self.preco_brl


class TipoLancamento(str, Enum):
    ALUGUEL_SHORT = "ALUGUEL_SHORT"
    AJUSTE = "AJUSTE"


@dataclass(frozen=True)
class Lancamento:
    """Movimento de caixa que não vem de uma ordem — aluguel de short, ajuste
    manual da mesa. Como o Trade, é linha imutável do ledger: o custo diário
    fica auditável em vez de sumir dentro de um cálculo.

    `valor` é assinado: negativo debita o caixa do fundo.
    """

    fundo: str
    tipo: TipoLancamento
    valor: Decimal
    executado_em: date
    descricao: str = ""

    @property
    def fluxo_caixa(self) -> Decimal:
        return self.valor


# Qualquer coisa que mexe no caixa e entra no ledger.
EventoCaixa = Trade | Lancamento


@dataclass(frozen=True)
class Fundo:
    nome: str
    caixa_inicial: Decimal
    inicio: date
    cotas_emitidas: Decimal = Decimal("1000000")


@dataclass(frozen=True)
class Fechamento:
    """Foto imutável de um fundo numa data. É a fonte do ranking."""

    fundo: str
    data: date
    caixa: Decimal
    valor_posicoes: Decimal
    patrimonio: Decimal
    cota: Decimal


@dataclass(frozen=True)
class Rejeicao:
    motivo: str


ResultadoValidacao = Trade | Rejeicao
