"""Curva do CDI: a taxa diária vigente em cada dia útil.

O caixa livre rende, em cada dia útil, o CDI **daquele dia** (regulamento §3.2).
A versão anterior do motor rendia o histórico inteiro com uma taxa só — a do dia
da apuração. Enquanto o Copom não mexia na Selic dava no mesmo; na primeira
mudança, todo o rendimento passado era refeito com a taxa nova e a cota saltava.

Cada registro da curva vale **a partir da sua data** até o registro seguinte.
Assim a curva serve tanto para a série diária do BCB quanto para o cadastro
manual da Mesa, que só lança uma linha quando o Copom muda a taxa.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Mapping

from .calendario import eh_dia_util

# 0,2% ao dia útil é ~65% ao ano: nenhum CDI real chega perto. O teto existe para
# barrar a troca mais provável no cadastro manual — digitar a porcentagem
# (0,0508) no lugar da fração (0,000508), o que multiplicaria o rendimento por 100.
TAXA_DIARIA_MAXIMA = Decimal("0.002")


class CDIIndisponivel(ValueError):
    """Não há taxa vigente para um dia que precisa render."""


@dataclass(frozen=True)
class CurvaCDI:
    vigencias: tuple[tuple[date, Decimal], ...]

    def __post_init__(self) -> None:
        datas = [d for d, _ in self.vigencias]
        if datas != sorted(set(datas)):
            raise ValueError("Curva do CDI com datas fora de ordem ou repetidas.")
        for dia, taxa in self.vigencias:
            validar_taxa(taxa, dia)

    @classmethod
    def de(cls, pontos: Mapping[date, Decimal] | Iterable[tuple[date, Decimal]]) -> CurvaCDI:
        itens = pontos.items() if isinstance(pontos, Mapping) else pontos
        return cls(tuple(sorted(itens)))

    @classmethod
    def constante(cls, taxa: Decimal, desde: date = date.min) -> CurvaCDI:
        return cls(((desde, taxa),))

    def taxa_em(self, dia: date) -> Decimal:
        """Taxa vigente no dia: a do último registro com data até `dia`."""
        posicao = bisect_right(self.vigencias, dia, key=lambda v: v[0])
        if posicao == 0:
            raise CDIIndisponivel(
                f"Sem CDI vigente em {dia:%d/%m/%Y}. Cadastre uma taxa com data igual "
                "ou anterior a essa (admin → Taxas CDI)."
            )
        return self.vigencias[posicao - 1][1]

    def fator(self, de: date, ate: date) -> Decimal:
        """Rendimento acumulado nos dias úteis de [de, ate), cada um à sua taxa.

        Mesma convenção de `calendario.dias_uteis`: o dia útil `d` rende de `d`
        para o dia útil seguinte, à taxa vigente em `d`. Sem dia útil, fator 1.
        """
        fator = Decimal(1)
        dia = de
        while dia < ate:
            if eh_dia_util(dia):
                fator *= Decimal(1) + self.taxa_em(dia)
            dia += timedelta(days=1)
        return fator


def validar_taxa(taxa: Decimal, dia: date | None = None) -> None:
    quando = f" em {dia:%d/%m/%Y}" if dia is not None and dia != date.min else ""
    if taxa < 0 or taxa > TAXA_DIARIA_MAXIMA:
        raise ValueError(
            f"CDI diário de {taxa}{quando} fora do plausível (0 a {TAXA_DIARIA_MAXIMA}). "
            "A taxa é a fração diária: 13,65% a.a. vira 0.00050788, não 0.050788."
        )
