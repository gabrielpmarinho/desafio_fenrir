"""Calendário de dias úteis brasileiro.

Sem dependências externas de propósito: o motor do Fenrir não deve precisar de
numpy nem de pacote de feriados para ser testado.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

# Feriados nacionais de data fixa (mês, dia).
_FIXOS = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)]

# Consciência Negra virou feriado nacional apenas a partir de 2024 (Lei 14.759/2023).
_ANO_CONSCIENCIA_NEGRA = 2024


def pascoa(ano: int) -> date:
    """Domingo de Páscoa pelo computus de Gauss/Meeus."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


@lru_cache(maxsize=None)
def feriados(ano: int) -> frozenset[date]:
    """Feriados nacionais de um ano, incluindo os móveis derivados da Páscoa."""
    dias = {date(ano, mes, dia) for mes, dia in _FIXOS}
    if ano >= _ANO_CONSCIENCIA_NEGRA:
        dias.add(date(ano, 11, 20))

    p = pascoa(ano)
    dias.update(
        {
            p - timedelta(days=48),  # Carnaval (segunda)
            p - timedelta(days=47),  # Carnaval (terça)
            p - timedelta(days=2),  # Sexta-feira Santa
            p + timedelta(days=60),  # Corpus Christi
        }
    )
    return frozenset(dias)


def eh_dia_util(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in feriados(dia.year)


def dias_uteis(inicio: date, fim: date) -> int:
    """Dias úteis no intervalo [inicio, fim), como a convenção de mercado.

    Retorna 0 se `fim` não for posterior a `inicio` — o motor nunca deve render
    juros para trás.
    """
    if fim <= inicio:
        return 0
    total = 0
    dia = inicio
    while dia < fim:
        if eh_dia_util(dia):
            total += 1
        dia += timedelta(days=1)
    return total


def proximo_dia_util(dia: date) -> date:
    while not eh_dia_util(dia):
        dia += timedelta(days=1)
    return dia


def dia_util_anterior(dia: date) -> date:
    while not eh_dia_util(dia):
        dia -= timedelta(days=1)
    return dia


def ultimo_dia_util_da_semana(ate: date) -> date:
    """Fecha a semana: a sexta da semana de `ate`, recuando se não for dia útil.

    Nunca devolve data futura — pedido numa quarta, entrega a sexta da semana
    anterior. É o corte do ranking: a foto só muda quando a semana termina.
    """
    sexta = ate + timedelta(days=4 - ate.weekday())
    if sexta > ate:
        sexta -= timedelta(days=7)
    return dia_util_anterior(sexta)
