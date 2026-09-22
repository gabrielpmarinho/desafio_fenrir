from __future__ import annotations

from datetime import date

from core import calendario


def test_pascoa_conhecida():
    assert calendario.pascoa(2026) == date(2026, 4, 5)
    assert calendario.pascoa(2027) == date(2027, 3, 28)


def test_feriados_moveis_derivam_da_pascoa():
    de_2026 = calendario.feriados(2026)
    assert date(2026, 2, 16) in de_2026  # Carnaval (segunda)
    assert date(2026, 2, 17) in de_2026  # Carnaval (terça)
    assert date(2026, 4, 3) in de_2026  # Sexta-feira Santa
    assert date(2026, 6, 4) in de_2026  # Corpus Christi


def test_consciencia_negra_so_vale_de_2024_em_diante():
    """Lei 14.759/2023. Incluir antes disso infla a contagem de dias úteis."""
    assert date(2023, 11, 20) not in calendario.feriados(2023)
    assert date(2024, 11, 20) in calendario.feriados(2024)


def test_dias_uteis_ignora_fim_de_semana():
    # segunda a sexta da mesma semana: [05/10, 09/10) = 4 dias
    assert calendario.dias_uteis(date(2026, 10, 5), date(2026, 10, 9)) == 4


def test_dias_uteis_desconta_feriado():
    # 12/10/2026 (segunda, Nossa Senhora Aparecida) não conta
    assert calendario.dias_uteis(date(2026, 10, 9), date(2026, 10, 16)) == 4


def test_dias_uteis_nao_anda_para_tras():
    assert calendario.dias_uteis(date(2026, 10, 9), date(2026, 10, 5)) == 0
    assert calendario.dias_uteis(date(2026, 10, 5), date(2026, 10, 5)) == 0


def test_proximo_dia_util_pula_fim_de_semana():
    assert calendario.proximo_dia_util(date(2026, 10, 10)) == date(2026, 10, 13)


def test_dia_util_anterior_volta_do_fim_de_semana():
    assert calendario.dia_util_anterior(date(2026, 10, 11)) == date(2026, 10, 9)


def test_semana_fecha_na_sexta():
    # Quarta, sábado e a própria sexta caem na mesma sexta.
    assert calendario.ultimo_dia_util_da_semana(date(2026, 9, 18)) == date(2026, 9, 18)
    assert calendario.ultimo_dia_util_da_semana(date(2026, 9, 19)) == date(2026, 9, 18)


def test_semana_nao_fecha_no_futuro():
    """Numa terça, o ranking mostra a sexta que já passou — nunca a que vem."""
    assert calendario.ultimo_dia_util_da_semana(date(2026, 9, 22)) == date(2026, 9, 18)


def test_semana_com_sexta_feriada_recua_para_quinta():
    # 03/04/2026 é Sexta-feira Santa.
    assert calendario.ultimo_dia_util_da_semana(date(2026, 4, 4)) == date(2026, 4, 2)
