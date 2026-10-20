"""Testes da curva do CDI.

O defeito que ela corrige: o motor rendia o histórico inteiro do caixa com uma
taxa só, a do dia da apuração. Na primeira mudança do Copom, todo o rendimento
passado era refeito com a taxa nova e a cota saltava.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from core import engine
from core.cdi import CDIIndisponivel, CurvaCDI
from core.models import Fundo

SEGUNDA = date(2026, 10, 5)
TERCA = date(2026, 10, 6)
QUARTA = date(2026, 10, 7)
SEXTA = date(2026, 10, 9)
SABADO = date(2026, 10, 10)
SEGUNDA_SEGUINTE = date(2026, 10, 19)  # 12/10 é feriado; usa a semana depois

ANTIGA = Decimal("0.0005")
NOVA = Decimal("0.0010")


@pytest.fixture
def fundo() -> Fundo:
    return Fundo(nome="Astra Capital", caixa_inicial=Decimal("100000000.00"), inicio=SEGUNDA)


def test_cada_dia_rende_a_taxa_vigente_nele():
    curva = CurvaCDI.de({SEGUNDA: ANTIGA, QUARTA: NOVA})

    # segunda e terça à taxa antiga, quarta e quinta à nova
    assert curva.fator(SEGUNDA, SEXTA) == (1 + ANTIGA) ** 2 * (1 + NOVA) ** 2


def test_mudar_a_taxa_nao_refaz_o_rendimento_passado(fundo):
    antes = engine.caixa(fundo, [], CurvaCDI.de({SEGUNDA: ANTIGA}), QUARTA)

    depois = engine.caixa(fundo, [], CurvaCDI.de({SEGUNDA: ANTIGA, QUARTA: NOVA}), QUARTA)

    assert depois == antes == Decimal("100000000.00") * (1 + ANTIGA) ** 2


def test_taxa_cadastrada_no_fim_de_semana_vale_a_partir_da_segunda():
    curva = CurvaCDI.de({SEGUNDA: ANTIGA, SABADO: NOVA})

    assert curva.taxa_em(SEXTA) == ANTIGA
    assert curva.taxa_em(SEGUNDA_SEGUINTE) == NOVA
    assert curva.fator(SEXTA, SEGUNDA_SEGUINTE) == (1 + ANTIGA) * (1 + NOVA) ** 4


def test_sem_taxa_vigente_e_erro_e_nao_rendimento_zero(fundo):
    curva = CurvaCDI.de({TERCA: ANTIGA})

    with pytest.raises(CDIIndisponivel, match="05/10/2026"):
        engine.caixa(fundo, [], curva, QUARTA)


def test_sem_dia_util_no_intervalo_o_fator_e_um():
    curva = CurvaCDI.de({SEGUNDA: ANTIGA})

    assert curva.fator(SABADO, SABADO) == 1
    assert curva.fator(SABADO, date(2026, 10, 11)) == 1


@pytest.mark.parametrize("taxa", [Decimal("0.0508"), Decimal("-0.0001")])
def test_taxa_fora_do_plausivel_e_recusada(taxa):
    # 0,0508 é o erro mais provável no cadastro: a porcentagem no lugar da fração
    with pytest.raises(ValueError, match="fração diária"):
        CurvaCDI.de({SEGUNDA: taxa})


def test_data_repetida_e_recusada():
    with pytest.raises(ValueError, match="repetidas"):
        CurvaCDI(((SEGUNDA, ANTIGA), (SEGUNDA, NOVA)))
