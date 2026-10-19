"""Rotina diária da Mesa, num comando só — é este que o agendador chama.

Para cada dia útil pendente, na ordem:

1. `puxar_precos`;
2. `liquidar_semana`, só no primeiro dia útil da semana (regulamento §2.1:
   segunda, ou o dia útil seguinte se a segunda for feriado);
3. `fechar_dia`.

Pode ser agendado de segunda a domingo: em dia não útil não faz nada. Se o
agendador falhou em algum dia (PC desligado, fonte de preço fora do ar), a
próxima execução recupera os dias úteis sem fechamento, em ordem.

Qualquer erro interrompe a sequência e o comando sai com código 1, para o
agendador registrar a falha. O que já foi gravado fica: os três comandos são
idempotentes, e a execução seguinte retoma do dia que faltou.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.calendario import eh_dia_util, proximo_dia_util
from desafio import models

# Mais do que isso sem fechamento é sinal de problema maior que um PC desligado:
# melhor alguém olhar antes de puxar duas semanas de preço de uma vez.
MAX_DIAS_RECUPERACAO = 10


class Command(BaseCommand):
    help = "Roda puxar_precos → liquidar_semana (1º dia útil da semana) → fechar_dia."

    def add_arguments(self, parser):
        parser.add_argument("--data", help="Data AAAA-MM-DD. Padrão: hoje.")
        parser.add_argument(
            "--desde",
            help="Reprocessa a partir desta data (AAAA-MM-DD), ignorando o teto "
            "de recuperação.",
        )

    def handle(self, *args, **opcoes):
        alvo = _resolver_data(opcoes.get("data"))
        desde = _resolver_data(opcoes["desde"]) if opcoes.get("desde") else None

        dias = self._dias_a_rodar(alvo, desde)
        if not dias:
            self.stdout.write(f"{alvo} não é dia útil e não há dia pendente. Nada a fazer.")
            return

        if len(dias) > 1:
            self.stdout.write(
                self.style.WARNING(
                    f"Recuperando {len(dias)} dias úteis: "
                    f"{dias[0]:%d/%m/%Y} a {dias[-1]:%d/%m/%Y}."
                )
            )

        for dia in dias:
            self._rodar_dia(dia)

    def _dias_a_rodar(self, alvo: date, desde: date | None) -> list[date]:
        if desde is not None:
            if desde > alvo:
                raise CommandError("--desde não pode ser posterior a --data.")
            return _dias_uteis_entre(desde, alvo)

        ultimo = (
            models.Fechamento.objects.filter(data__lte=alvo)
            .order_by("-data")
            .values_list("data", flat=True)
            .first()
        )
        if ultimo is None:
            return [alvo] if eh_dia_util(alvo) else []

        dias = _dias_uteis_entre(ultimo + timedelta(days=1), alvo)
        if len(dias) > MAX_DIAS_RECUPERACAO:
            raise CommandError(
                f"Último fechamento em {ultimo:%d/%m/%Y}: são {len(dias)} dias úteis "
                f"pendentes (teto {MAX_DIAS_RECUPERACAO}). Confira o motivo e rode "
                "à mão com --desde."
            )
        # Fechamento de hoje já gravado: roda de novo assim mesmo. Os comandos
        # são idempotentes, e uma segunda execução pode completar preço faltante.
        if not dias and eh_dia_util(alvo):
            dias = [alvo]
        return dias

    def _rodar_dia(self, dia: date):
        texto = dia.isoformat()
        self.stdout.write(self.style.MIGRATE_HEADING(f"== {dia:%d/%m/%Y} =="))

        call_command("puxar_precos", data=texto, stdout=self.stdout, stderr=self.stderr)
        if eh_dia_de_liquidacao(dia):
            call_command(
                "liquidar_semana", data=texto, stdout=self.stdout, stderr=self.stderr
            )
        call_command("fechar_dia", data=texto, stdout=self.stdout, stderr=self.stderr)


def eh_dia_de_liquidacao(dia: date) -> bool:
    """Primeiro dia útil da semana de `dia` (regulamento §2.1)."""
    segunda = dia - timedelta(days=dia.weekday())
    return proximo_dia_util(segunda) == dia


def _dias_uteis_entre(inicio: date, fim: date) -> list[date]:
    """Dias úteis em [inicio, fim]."""
    dias = []
    dia = inicio
    while dia <= fim:
        if eh_dia_util(dia):
            dias.append(dia)
        dia += timedelta(days=1)
    return dias


def _resolver_data(texto: str | None) -> date:
    if not texto:
        return date.today()
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as erro:
        raise CommandError("Data inválida. Use AAAA-MM-DD.") from erro
