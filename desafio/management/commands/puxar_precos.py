"""Coleta preços de fechamento, câmbio e CDI de um dia.

Roda todo dia útil, depois do fechamento do mercado americano, antes do
`fechar_dia`.
"""

from __future__ import annotations

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from core.calendario import eh_dia_util
from desafio.servicos import precos


class Command(BaseCommand):
    help = "Busca e grava os preços de fechamento, o câmbio e o CDI do dia."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data",
            help="Data no formato AAAA-MM-DD. Padrão: hoje.",
        )

    def handle(self, *args, **opcoes):
        dia = _resolver_data(opcoes.get("data"))

        if not eh_dia_util(dia):
            self.stdout.write(self.style.WARNING(f"{dia} não é dia útil. Nada a fazer."))
            return

        cambio = precos.puxar_cambio(dia)
        if cambio is None:
            raise CommandError(
                f"Sem cotação USD/BRL para {dia}. Sem câmbio não dá para marcar "
                "ativo estrangeiro — a apuração do dia não pode rodar."
            )
        self.stdout.write(f"USD/BRL: {cambio}")

        cdi = precos.puxar_cdi(dia)
        if cdi is None:
            self.stdout.write(
                self.style.WARNING("CDI indisponível no BCB; será usado o último gravado.")
            )
        else:
            self.stdout.write(f"CDI diário: {cdi}")

        gravados, faltando = precos.puxar_precos(dia)
        self.stdout.write(self.style.SUCCESS(f"{gravados} preços gravados."))

        indices, sem_indice = precos.puxar_benchmarks(dia)
        self.stdout.write(self.style.SUCCESS(f"{indices} benchmarks gravados."))
        if sem_indice:
            self.stdout.write(
                self.style.WARNING(
                    f"Sem benchmark para: {', '.join(sem_indice)}. O gráfico da "
                    "carteira fica com furo nesse dia, a apuração não é afetada."
                )
            )

        if faltando:
            self.stdout.write(
                self.style.WARNING(
                    f"Sem preço para: {', '.join(faltando)}. "
                    "Confira se é feriado no mercado do ativo antes de seguir."
                )
            )


def _resolver_data(texto: str | None) -> date:
    if not texto:
        return date.today()
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as erro:
        raise CommandError("Data inválida. Use AAAA-MM-DD.") from erro
