"""Custos de carrego do Desafio Fenrir.

Regra copiada do Desafio JGP (regulamento, "Custos de Execução", item i):

    Vendas "SHORT" => custo de 0,4% ao mês do financeiro da posição.
    Cada dia em uma posição SHORT custa 1/20 do valor mensal.

O custo é **linear** no tamanho da posição. A tabela progressiva do regulamento
do JGP é outra coisa — slippage de ordens STOP/ON STOP —, e o Fenrir só opera a
mercado. Ver `custo_execucao_progressivo` no fim do arquivo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from .models import Lancamento, TipoLancamento

CUSTO_ALUGUEL_MENSAL = Decimal("0.004")  # 0,4% a.m.
DIAS_UTEIS_NO_MES = 20  # "1/20 do valor mensal" por dia
CUSTO_ALUGUEL_DIARIO = CUSTO_ALUGUEL_MENSAL / DIAS_UTEIS_NO_MES  # 0,02% a.d.


def financeiro_vendido(
    posicoes: Mapping[str, int],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
) -> Decimal:
    """Soma, em módulo e em BRL, apenas das posições vendidas."""
    total = Decimal(0)
    for ticker, quantidade in posicoes.items():
        if quantidade >= 0:
            continue
        total += abs(Decimal(quantidade)) * precos[ticker] * cambios.get(ticker, Decimal(1))
    return total


def custo_aluguel_do_dia(
    posicoes: Mapping[str, int],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
) -> Decimal:
    """Custo de um dia de carrego, marcado pelo fechamento do próprio dia.

    Cobrado por dia útil em que a posição está aberta no fechamento, inclusive o
    dia em que foi montada.
    """
    return financeiro_vendido(posicoes, precos, cambios) * CUSTO_ALUGUEL_DIARIO


def lancamento_aluguel(
    fundo: str,
    posicoes: Mapping[str, int],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
    dia: date,
) -> Lancamento | None:
    """Lançamento de débito do dia, ou None se o fundo não está vendido."""
    custo = custo_aluguel_do_dia(posicoes, precos, cambios)
    if custo <= 0:
        return None

    vendidos = sorted(t for t, q in posicoes.items() if q < 0)
    return Lancamento(
        fundo=fundo,
        tipo=TipoLancamento.ALUGUEL_SHORT,
        valor=-custo,
        executado_em=dia,
        descricao=f"Aluguel 0,4% a.m. sobre {', '.join(vendidos)}",
    )


# --------------------------------------------------------------------------
# Não usado hoje — fica documentado caso o Fenrir passe a ter ordens stop.
# --------------------------------------------------------------------------
_FAIXAS_SLIPPAGE = [
    (Decimal("10000000"), Decimal("0")),
    (Decimal("30000000"), Decimal("0.001")),
    (Decimal("60000000"), Decimal("0.002")),
    (Decimal("80000000"), Decimal("0.003")),
]
_SLIPPAGE_ACIMA_DA_ULTIMA_FAIXA = Decimal("0.004")


def custo_execucao_progressivo(financeiro: Decimal) -> Decimal:
    """Slippage do JGP por faixa de financeiro (ordens STOP/ON STOP).

    Devolve o percentual a piorar no preço de execução. O Fenrir não usa —
    está aqui para o caso de o regulamento passar a aceitar ordens stop.
    """
    for teto, percentual in _FAIXAS_SLIPPAGE:
        if financeiro <= teto:
            return percentual
    return _SLIPPAGE_ACIMA_DA_ULTIMA_FAIXA
