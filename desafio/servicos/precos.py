"""Coleta de preços de fechamento, câmbio e CDI.

Único ponto do sistema que fala com a internet. Tudo que entra aqui é
persistido — a apuração lê do banco, nunca da API.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import requests
import yfinance as yf

from core.universo import UNIVERSO

from .. import models

logger = logging.getLogger(__name__)

# Série 12 do SGS é o CDI diário. A série 11 é a Selic — a versão antiga do
# terminal usava a 11 por engano.
URL_CDI = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json"
TICKER_CAMBIO = "USDBRL=X"

# Índices de referência do gráfico da carteira. Não são investíveis: ficam fora
# do UNIVERSO e em tabela própria, para não entrarem no preço de apuração.
BENCHMARKS = {"IBOV": "^BVSP", "SP500": "^GSPC"}


class PrecoIndisponivel(Exception):
    pass


def _fechamento(ticker: str, dia: date) -> Decimal | None:
    """Fechamento do ticker no dia. None se o papel não negociou.

    Nunca cai para o dia anterior: a apuração de um dia usa o preço daquele dia
    ou não usa preço nenhum. Preencher buraco com preço velho falsifica cota.
    """
    try:
        # `end` é exclusivo no yfinance.
        historico = yf.Ticker(ticker).history(start=dia, end=dia + timedelta(days=1))
    except Exception:
        logger.exception("Falha ao buscar %s em %s", ticker, dia)
        return None

    if historico.empty:
        return None

    do_dia = historico[historico.index.date == dia]
    if do_dia.empty:
        return None

    try:
        return Decimal(str(round(float(do_dia["Close"].iloc[-1]), 8)))
    except (InvalidOperation, ValueError):
        return None


def puxar_precos(dia: date) -> tuple[int, list[str]]:
    """Grava o fechamento de todos os ativos da whitelist. Idempotente.

    Devolve (quantos gravou, tickers que falharam).
    """
    gravados, faltando = 0, []
    for ticker in UNIVERSO:
        if models.PrecoFechamento.objects.filter(ticker=ticker, data=dia).exists():
            continue
        preco = _fechamento(ticker, dia)
        if preco is None or preco <= 0:
            faltando.append(ticker)
            continue
        models.PrecoFechamento.objects.create(ticker=ticker, data=dia, preco=preco)
        gravados += 1
    return gravados, faltando


def puxar_cambio(dia: date) -> Decimal | None:
    if (existente := models.Cotacao.objects.filter(data=dia).first()) is not None:
        return existente.usd_brl

    valor = _fechamento(TICKER_CAMBIO, dia)
    if valor is None:
        return None
    models.Cotacao.objects.create(data=dia, usd_brl=valor)
    return valor


def puxar_cdi(dia: date) -> Decimal | None:
    """CDI diário do BCB, em fração (0,0005 = 0,05% a.d.)."""
    if (existente := models.TaxaCDI.objects.filter(data=dia).first()) is not None:
        return existente.taxa_diaria

    try:
        resposta = requests.get(URL_CDI, timeout=20)
        resposta.raise_for_status()
        percentual = Decimal(str(resposta.json()[0]["valor"]))
    except Exception:
        logger.exception("Falha ao buscar CDI no BCB")
        return None

    taxa = percentual / Decimal("100")
    models.TaxaCDI.objects.create(data=dia, taxa_diaria=taxa)
    return taxa


def puxar_benchmarks(dia: date) -> tuple[int, list[str]]:
    """Grava o fechamento do IBOV e do S&P. Idempotente, como as demais."""
    gravados, faltando = 0, []
    for codigo, ticker in BENCHMARKS.items():
        if models.Benchmark.objects.filter(codigo=codigo, data=dia).exists():
            continue
        valor = _fechamento(ticker, dia)
        if valor is None or valor <= 0:
            faltando.append(codigo)
            continue
        models.Benchmark.objects.create(codigo=codigo, data=dia, valor=valor)
        gravados += 1
    return gravados, faltando
