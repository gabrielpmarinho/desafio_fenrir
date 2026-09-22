"""Tradução entre as tabelas do Django e os tipos do motor.

Fronteira única: só este módulo conhece os dois lados. `core/` continua sem
saber que Django existe, e os modelos continuam sem saber calcular nada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.models import EventoCaixa
from core.models import Fundo as FundoCore
from core.models import Lancamento as LancamentoCore
from core.models import TipoLancamento
from core.models import Trade as TradeCore
from core.universo import UNIVERSO

from . import models


def para_core_fundo(fundo: models.Fundo) -> FundoCore:
    return FundoCore(
        nome=fundo.nome,
        caixa_inicial=fundo.caixa_inicial,
        inicio=fundo.inicio,
        cotas_emitidas=fundo.cotas_emitidas,
    )


def para_core_trade(trade: models.Trade) -> TradeCore:
    return TradeCore(
        fundo=trade.fundo.nome,
        ticker=trade.ticker,
        quantidade=trade.quantidade,
        preco_nativo=trade.preco_nativo,
        cambio=trade.cambio,
        executado_em=trade.executado_em,
    )


def para_core_lancamento(lancamento: models.Lancamento) -> LancamentoCore:
    return LancamentoCore(
        fundo=lancamento.fundo.nome,
        tipo=TipoLancamento(lancamento.tipo),
        valor=lancamento.valor,
        executado_em=lancamento.executado_em,
        descricao=lancamento.descricao,
    )


def eventos_do_fundo(fundo: models.Fundo, ate: date | None = None) -> list[EventoCaixa]:
    """Ledger completo do fundo, já no formato do motor."""
    trades = fundo.trades.select_related("fundo").all()
    lancamentos = fundo.lancamentos.select_related("fundo").all()
    if ate is not None:
        trades = trades.filter(executado_em__lte=ate)
        lancamentos = lancamentos.filter(executado_em__lte=ate)

    return [
        *(para_core_trade(t) for t in trades),
        *(para_core_lancamento(l) for l in lancamentos),
    ]


def precos_do_dia(dia: date) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """Preços de fechamento e câmbios do dia, na forma que o motor espera.

    Levanta erro se faltar a cotação do dólar e houver ativo estrangeiro — a
    apuração não pode rodar pela metade.
    """
    precos = {
        p.ticker: p.preco for p in models.PrecoFechamento.objects.filter(data=dia)
    }

    tem_estrangeiro = any(
        UNIVERSO[t].estrangeiro for t in precos if t in UNIVERSO
    )
    cotacao = models.Cotacao.objects.filter(data=dia).first()
    if tem_estrangeiro and cotacao is None:
        raise ValueError(f"Sem cotação USD/BRL para {dia:%d/%m/%Y}.")

    cambios = {
        ticker: (cotacao.usd_brl if UNIVERSO[ticker].estrangeiro else Decimal("1"))
        for ticker in precos
        if ticker in UNIVERSO
    }
    return precos, cambios


def taxa_cdi_do_dia(dia: date) -> Decimal:
    """Último CDI divulgado até o dia. O BCB publica com defasagem."""
    taxa = (
        models.TaxaCDI.objects.filter(data__lte=dia).order_by("-data").first()
    )
    if taxa is None:
        raise ValueError(
            "Nenhuma taxa CDI cadastrada. Rode `manage.py puxar_precos` antes."
        )
    return taxa.taxa_diaria
