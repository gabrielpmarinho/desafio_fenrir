from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from core import metricas
from core.models import Fechamento


def _serie(cotas: list[str]) -> list[Fechamento]:
    base = date(2026, 10, 9)
    return [
        Fechamento(
            fundo="Astra Capital",
            data=base + timedelta(weeks=i),
            caixa=Decimal("0"),
            valor_posicoes=Decimal("0"),
            patrimonio=Decimal(c) * 1_000_000,
            cota=Decimal(c),
        )
        for i, c in enumerate(cotas)
    ]


def test_retornos_entre_fechamentos():
    serie = metricas.retornos(_serie(["100.00", "110.00", "99.00"]))

    assert serie[0] == pytest.approx(0.10)
    assert serie[1] == pytest.approx(-0.10)


def test_volatilidade_exige_duas_observacoes():
    assert metricas.volatilidade_anualizada([0.01]) is None


def test_volatilidade_zero_quando_retorno_e_constante():
    assert metricas.volatilidade_anualizada([0.01, 0.01, 0.01]) == 0.0


def test_sharpe_positivo_quando_bate_o_cdi():
    serie = [0.010, 0.012, 0.008, 0.011]

    resultado = metricas.sharpe(serie, retorno_livre_risco_periodo=0.002)

    assert resultado is not None and resultado > 0


def test_sharpe_negativo_quando_perde_do_cdi():
    serie = [0.001, 0.002, -0.001, 0.000]

    resultado = metricas.sharpe(serie, retorno_livre_risco_periodo=0.002)

    assert resultado is not None and resultado < 0


def test_sharpe_sem_volatilidade_retorna_none():
    """Sharpe infinito não serve para ranking."""
    assert metricas.sharpe([0.01, 0.01, 0.01], 0.002) is None


def test_retorno_acumulado_usa_primeira_e_ultima_cota():
    resultado = metricas.retorno_acumulado(_serie(["100.00", "80.00", "125.00"]))

    assert resultado == Decimal("25")
