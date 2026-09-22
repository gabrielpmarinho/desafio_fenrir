"""Testes do motor.

Os quatro primeiros são os casos que a versão anterior (Streamlit + Sheets)
executava errado por causa do bloco de custódia duplicado em app.py:286-300.
Ficam aqui como regressão permanente.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from core import engine
from core.models import Direcao, Fundo, Ordem, Rejeicao, Trade
from core.universo import UNIVERSO

CDI_DIARIO = Decimal("0.0005")  # ~13,3% a.a. em 252 dias úteis
INICIO = date(2026, 10, 5)  # segunda-feira
EXECUCAO = date(2026, 10, 12)  # segunda seguinte

PRECOS = {
    "PETR4.SA": Decimal("40.00"),
    "VALE3.SA": Decimal("60.00"),
    "ITUB4.SA": Decimal("35.00"),
    "SPY": Decimal("500.00"),
}
CAMBIOS = {"SPY": Decimal("5.40")}


@pytest.fixture
def fundo() -> Fundo:
    return Fundo(
        nome="Astra Capital",
        caixa_inicial=Decimal("100000000.00"),
        inicio=INICIO,
    )


def _boleta(ticker: str, quantidade: int, direcao: Direcao) -> Ordem:
    return Ordem(
        fundo="Astra Capital",
        ticker=ticker,
        quantidade=quantidade,
        direcao=direcao,
        enviada_em=datetime(2026, 10, 11, 10, 0),
    )


def _executar(fundo: Fundo, ordem: Ordem, ledger: list[Trade]) -> Trade | Rejeicao:
    return engine.executar(
        ordem, fundo, ledger, UNIVERSO, PRECOS, CAMBIOS, CDI_DIARIO, EXECUCAO
    )


def _trade(ticker: str, quantidade: int, preco: str, quando: date = INICIO) -> Trade:
    return Trade(
        fundo="Astra Capital",
        ticker=ticker,
        quantidade=quantidade,
        preco_nativo=Decimal(preco),
        cambio=Decimal("1"),
        executado_em=quando,
    )


# --------------------------------------------------------------------------
# Regressão: os quatro casos quebrados na versão antiga
# --------------------------------------------------------------------------
def test_compra_em_carteira_vazia_nao_duplica_quantidade(fundo):
    """Antes: comprar 100 entregava 200 ações pelo preço de 100."""
    trade = _executar(fundo, _boleta("PETR4.SA", 100, Direcao.COMPRA), [])

    assert isinstance(trade, Trade)
    assert engine.posicoes([trade]) == {"PETR4.SA": 100}
    assert trade.fluxo_caixa == Decimal("-4000.00")


def test_venda_a_descoberto_abre_posicao_negativa(fundo):
    """Antes: a posição short sumia e o caixa ficava com o crédito. Dinheiro grátis."""
    trade = _executar(fundo, _boleta("VALE3.SA", 100, Direcao.VENDA), [])

    assert isinstance(trade, Trade)
    assert engine.posicoes([trade]) == {"VALE3.SA": -100}
    assert trade.fluxo_caixa == Decimal("6000.00")


def test_venda_parcial_preserva_o_restante(fundo):
    """Antes: vender 100 de uma posição de 200 apagava as 200."""
    ledger = [_trade("ITUB4.SA", 200, "35.00")]

    trade = _executar(fundo, _boleta("ITUB4.SA", 100, Direcao.VENDA), ledger)

    assert isinstance(trade, Trade)
    assert engine.posicoes([*ledger, trade]) == {"ITUB4.SA": 100}


def test_compra_adicional_soma_sem_duplicar(fundo):
    """Antes: 100 + 100 virava 300."""
    ledger = [_trade("PETR4.SA", 100, "40.00")]

    trade = _executar(fundo, _boleta("PETR4.SA", 100, Direcao.COMPRA), ledger)

    assert isinstance(trade, Trade)
    assert engine.posicoes([*ledger, trade]) == {"PETR4.SA": 200}


def test_posicao_zerada_some_da_carteira(fundo):
    ledger = [_trade("PETR4.SA", 100, "40.00")]

    trade = _executar(fundo, _boleta("PETR4.SA", 100, Direcao.VENDA), ledger)

    assert engine.posicoes([*ledger, trade]) == {}


# --------------------------------------------------------------------------
# CDI
# --------------------------------------------------------------------------
def test_cdi_capitaliza_no_caixa_parado(fundo):
    saldo = engine.caixa(fundo, [], CDI_DIARIO, date(2026, 10, 9))  # 4 dias úteis

    esperado = Decimal("100000000.00") * (Decimal("1.0005") ** 4)
    assert saldo == esperado
    assert saldo > fundo.caixa_inicial


def test_operar_nao_apaga_o_cdi_acumulado(fundo):
    """Antes: liquidar uma ordem sobrescrevia o caixa com o valor sem juros
    e reiniciava o relógio — quem operava perdia todo o CDI do período."""
    compra = _trade("PETR4.SA", 100, "40.00", quando=date(2026, 10, 9))

    saldo = engine.caixa(fundo, [compra], CDI_DIARIO, date(2026, 10, 9))

    juros_ate_a_compra = Decimal("100000000.00") * (Decimal("1.0005") ** 4)
    assert saldo == juros_ate_a_compra - Decimal("4000.00")


def test_cdi_nao_rende_para_tras(fundo):
    assert engine.caixa(fundo, [], CDI_DIARIO, INICIO) == fundo.caixa_inicial


# --------------------------------------------------------------------------
# Limite de alavancagem (regulamento §3.2)
# --------------------------------------------------------------------------
def test_compra_acima_do_patrimonio_e_rejeitada(fundo):
    # 3.000.000 ações x R$ 40 = R$ 120 milhões > R$ 100 milhões de patrimônio
    resultado = _executar(fundo, _boleta("PETR4.SA", 3_000_000, Direcao.COMPRA), [])

    assert isinstance(resultado, Rejeicao)
    assert "Alavancagem" in resultado.motivo


def test_compra_no_limite_do_patrimonio_passa(fundo):
    resultado = _executar(fundo, _boleta("PETR4.SA", 2_500_000, Direcao.COMPRA), [])

    assert isinstance(resultado, Trade)


def test_short_tambem_consome_limite(fundo):
    """Comprado e vendido somam em módulo — short não é exposição grátis."""
    ledger = [_trade("PETR4.SA", 2_400_000, "40.00")]  # R$ 96 mi comprados

    resultado = _executar(fundo, _boleta("VALE3.SA", 200_000, Direcao.VENDA), ledger)

    assert isinstance(resultado, Rejeicao)  # +R$ 12 mi vendidos estoura o limite


def test_ticker_fora_da_whitelist_e_rejeitado(fundo):
    resultado = _executar(fundo, _boleta("TSLA", 1, Direcao.COMPRA), [])

    assert isinstance(resultado, Rejeicao)
    assert "whitelist" in resultado.motivo


# --------------------------------------------------------------------------
# Câmbio
# --------------------------------------------------------------------------
def test_ativo_estrangeiro_converte_para_reais(fundo):
    trade = _executar(fundo, _boleta("SPY", 100, Direcao.COMPRA), [])

    assert isinstance(trade, Trade)
    assert trade.preco_brl == Decimal("2700.00")  # 500 USD x 5,40
    assert trade.fluxo_caixa == Decimal("-270000.00")


# --------------------------------------------------------------------------
# Lote e fechamento
# --------------------------------------------------------------------------
def test_lote_valida_contra_as_ordens_anteriores(fundo):
    """Duas ordens individualmente válidas não podem estourar o limite juntas."""
    fundos = {fundo.nome: fundo}
    ordens = [
        Ordem(fundo.nome, "PETR4.SA", 2_000_000, Direcao.COMPRA, datetime(2026, 10, 11, 9)),
        Ordem(fundo.nome, "PETR4.SA", 2_000_000, Direcao.COMPRA, datetime(2026, 10, 11, 10)),
    ]

    resultados = engine.executar_lote(
        ordens, fundos, [], UNIVERSO, PRECOS, CAMBIOS, CDI_DIARIO, EXECUCAO
    )

    assert [type(r) for _, r in resultados] == [Trade, Rejeicao]
    # o resultado vem colado na boleta que o originou, na ordem de chegada
    assert resultados[0][0].enviada_em.hour == 9
    assert resultados[1][0].enviada_em.hour == 10  # a segunda a chegar é a barrada


def test_cota_inicial_vale_100(fundo):
    fechamento = engine.fechar(fundo, [], PRECOS, CAMBIOS, CDI_DIARIO, INICIO)

    assert fechamento.cota == Decimal("100.00")
    assert fechamento.patrimonio == Decimal("100000000.00")


def test_fechamento_marca_posicao_a_mercado(fundo):
    ledger = [_trade("PETR4.SA", 100, "40.00")]
    precos_novos = {**PRECOS, "PETR4.SA": Decimal("44.00")}

    fechamento = engine.fechar(fundo, ledger, precos_novos, CAMBIOS, CDI_DIARIO, INICIO)

    assert fechamento.valor_posicoes == Decimal("4400.00")
    assert fechamento.caixa == Decimal("99996000.00")
    assert fechamento.patrimonio == Decimal("100000400.00")


def test_fechamento_ignora_trades_de_outro_fundo(fundo):
    intruso = Trade("Citadel Capital", "PETR4.SA", 500, Decimal("40"), Decimal("1"), INICIO)

    fechamento = engine.fechar(fundo, [intruso], PRECOS, CAMBIOS, CDI_DIARIO, INICIO)

    assert fechamento.valor_posicoes == Decimal("0.00")
    assert fechamento.patrimonio == Decimal("100000000.00")


# --------------------------------------------------------------------------
# Invariantes dos tipos
# --------------------------------------------------------------------------
def test_boleta_com_quantidade_zero_nao_existe():
    with pytest.raises(ValueError):
        _boleta("PETR4.SA", 0, Direcao.COMPRA)


def test_trade_exige_preco_positivo():
    with pytest.raises(ValueError):
        Trade("Astra Capital", "PETR4.SA", 100, Decimal("0"), Decimal("1"), INICIO)
