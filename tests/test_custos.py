"""Custo de carrego do short — regra do JGP: 0,4% a.m., 1/20 por dia."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from core import custos, engine
from core.models import Fundo, Lancamento, TipoLancamento, Trade

INICIO = date(2026, 10, 5)  # segunda
CDI_DIARIO = Decimal("0.0005")
PRECOS = {"VALE3.SA": Decimal("60.00"), "PETR4.SA": Decimal("40.00")}
CAMBIOS: dict[str, Decimal] = {}

FUNDO = Fundo("Astra Capital", Decimal("100000000.00"), INICIO)


def _short(ticker: str, quantidade: int, preco: str, quando: date = INICIO) -> Trade:
    return Trade("Astra Capital", ticker, -quantidade, Decimal(preco), Decimal("1"), quando)


def test_taxa_diaria_e_um_vinte_avos_da_mensal():
    assert custos.CUSTO_ALUGUEL_DIARIO == Decimal("0.004") / 20
    assert custos.CUSTO_ALUGUEL_DIARIO == Decimal("0.0002")  # 0,02% a.d.


def test_custo_incide_so_sobre_a_parte_vendida():
    posicoes = {"VALE3.SA": -1000, "PETR4.SA": 2000}

    financeiro = custos.financeiro_vendido(posicoes, PRECOS, CAMBIOS)

    assert financeiro == Decimal("60000.00")  # ignora os R$ 80.000 comprados


def test_custo_do_dia_e_linear_no_tamanho():
    """Linear, não progressivo: dobrar a posição dobra o custo."""
    um = custos.custo_aluguel_do_dia({"VALE3.SA": -1000}, PRECOS, CAMBIOS)
    dois = custos.custo_aluguel_do_dia({"VALE3.SA": -2000}, PRECOS, CAMBIOS)

    assert um == Decimal("12.00")  # 60.000 x 0,02%
    assert dois == um * 2


def test_carteira_sem_short_nao_gera_lancamento():
    lancamento = custos.lancamento_aluguel(
        "Astra Capital", {"PETR4.SA": 1000}, PRECOS, CAMBIOS, INICIO
    )

    assert lancamento is None


def test_lancamento_debita_o_caixa():
    lancamento = custos.lancamento_aluguel(
        "Astra Capital", {"VALE3.SA": -1000}, PRECOS, CAMBIOS, INICIO
    )

    assert lancamento is not None
    assert lancamento.tipo is TipoLancamento.ALUGUEL_SHORT
    assert lancamento.valor == Decimal("-12.00")
    assert lancamento.fluxo_caixa < 0
    assert "VALE3.SA" in lancamento.descricao


def test_apurar_dia_devolve_o_aluguel_do_dia():
    ledger = [_short("VALE3.SA", 1000, "60.00")]

    fechamento, aluguel = engine.apurar_dia(
        FUNDO, ledger, PRECOS, CAMBIOS, CDI_DIARIO, INICIO
    )

    assert aluguel is not None and aluguel.valor == Decimal("-12.00")
    # caixa = 100mm + 60.000 do short - 12 de aluguel
    assert fechamento.caixa == Decimal("100060000.00") - Decimal("12.00")
    assert fechamento.valor_posicoes == Decimal("-60000.00")


def test_custo_acumula_a_cada_dia_que_a_posicao_fica_aberta():
    """O ledger de cada dia precisa ser persistido para o custo somar."""
    ledger: list = [_short("VALE3.SA", 1000, "60.00")]

    for dia in (date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)):
        _, aluguel = engine.apurar_dia(FUNDO, ledger, PRECOS, CAMBIOS, CDI_DIARIO, dia)
        assert aluguel is not None
        ledger.append(aluguel)

    debitos = [e for e in ledger if isinstance(e, Lancamento)]
    assert len(debitos) == 3
    assert sum(d.valor for d in debitos) == Decimal("-36.00")


def test_posicao_fechada_para_de_pagar_aluguel():
    ledger = [
        _short("VALE3.SA", 1000, "60.00"),
        Trade("Astra Capital", "VALE3.SA", 1000, Decimal("60"), Decimal("1"), date(2026, 10, 6)),
    ]

    _, aluguel = engine.apurar_dia(
        FUNDO, ledger, PRECOS, CAMBIOS, CDI_DIARIO, date(2026, 10, 6)
    )

    assert aluguel is None


def test_lancamento_nao_vira_posicao():
    """O ledger é misto; `posicoes` só pode enxergar trades."""
    ledger = [
        _short("VALE3.SA", 1000, "60.00"),
        Lancamento("Astra Capital", TipoLancamento.ALUGUEL_SHORT, Decimal("-12"), INICIO),
    ]

    assert engine.posicoes(ledger) == {"VALE3.SA": -1000}


def test_tabela_progressiva_e_slippage_de_ordem_stop_nao_aluguel():
    """Guarda a regra certa: a progressão do JGP é por faixa de financeiro e vale
    para ordens STOP/ON STOP, que o Fenrir não tem."""
    assert custos.custo_execucao_progressivo(Decimal("5000000")) == Decimal("0")
    assert custos.custo_execucao_progressivo(Decimal("30000000")) == Decimal("0.001")
    assert custos.custo_execucao_progressivo(Decimal("60000000")) == Decimal("0.002")
    assert custos.custo_execucao_progressivo(Decimal("80000000")) == Decimal("0.003")
    assert custos.custo_execucao_progressivo(Decimal("100000000")) == Decimal("0.004")
