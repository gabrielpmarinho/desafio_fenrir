"""Métricas de risco do regulamento §6.2.

Calculadas sobre a série de cotas de fechamento — por isso o fechamento precisa
ser gravado como linha imutável, e não recalculado com preço ao vivo.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Sequence

from .models import Fechamento

# A cota do Fenrir muda uma vez por dia útil, no fechamento — então a série é
# diária e anualiza por 252, não por 52.
DIAS_UTEIS_NO_ANO = 252


def retornos(fechamentos: Sequence[Fechamento]) -> list[float]:
    """Retornos simples entre fechamentos consecutivos, em ordem cronológica."""
    ordenados = sorted(fechamentos, key=lambda f: f.data)
    serie = []
    for anterior, atual in zip(ordenados, ordenados[1:]):
        if anterior.cota == 0:
            continue
        serie.append(float(atual.cota / anterior.cota) - 1.0)
    return serie


def volatilidade_anualizada(
    serie: Sequence[float], periodos_por_ano: int = DIAS_UTEIS_NO_ANO
) -> float | None:
    """Desvio padrão amostral anualizado. None se não houver amostra suficiente."""
    if len(serie) < 2:
        return None
    media = sum(serie) / len(serie)
    variancia = sum((r - media) ** 2 for r in serie) / (len(serie) - 1)
    return math.sqrt(variancia) * math.sqrt(periodos_por_ano)


def sharpe(
    serie: Sequence[float],
    retorno_livre_risco_periodo: float,
    periodos_por_ano: int = DIAS_UTEIS_NO_ANO,
) -> float | None:
    """Sharpe anualizado usando o CDI do período como taxa livre de risco.

    Devolve None quando não há amostra suficiente ou quando a volatilidade é
    zero — Sharpe infinito não significa nada para o ranking.
    """
    if len(serie) < 2:
        return None
    excesso = [r - retorno_livre_risco_periodo for r in serie]
    media = sum(excesso) / len(excesso)
    variancia = sum((r - media) ** 2 for r in excesso) / (len(excesso) - 1)
    desvio = math.sqrt(variancia)
    if desvio == 0:
        return None
    return (media / desvio) * math.sqrt(periodos_por_ano)


def retorno_acumulado(fechamentos: Sequence[Fechamento]) -> Decimal | None:
    """Variação percentual entre a primeira e a última cota (regulamento §6.2)."""
    ordenados = sorted(fechamentos, key=lambda f: f.data)
    if len(ordenados) < 2 or ordenados[0].cota == 0:
        return None
    return (ordenados[-1].cota / ordenados[0].cota - 1) * 100
