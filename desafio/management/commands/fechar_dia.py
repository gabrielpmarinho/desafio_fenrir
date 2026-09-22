"""Apuração diária das cotas.

Roda todo dia útil depois do `puxar_precos`. Para cada fundo: marca as posições
pelo fechamento do dia, cobra o aluguel de short e grava a foto da cota.

Idempotente: rodar duas vezes no mesmo dia não cobra aluguel em dobro nem
duplica fechamento.
"""

from __future__ import annotations

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import engine
from core.calendario import eh_dia_util
from desafio import adapters, models


class Command(BaseCommand):
    help = "Apura a cota de todos os fundos ativos no dia."

    def add_arguments(self, parser):
        parser.add_argument("--data", help="Data AAAA-MM-DD. Padrão: hoje.")
        parser.add_argument(
            "--refazer",
            action="store_true",
            help="Apaga a apuração existente do dia e refaz. Use com cuidado.",
        )

    def handle(self, *args, **opcoes):
        dia = _resolver_data(opcoes.get("data"))
        refazer = opcoes["refazer"]

        if not eh_dia_util(dia):
            self.stdout.write(self.style.WARNING(f"{dia} não é dia útil. Nada a apurar."))
            return

        try:
            precos, cambios = adapters.precos_do_dia(dia)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro

        if not precos:
            raise CommandError(
                f"Nenhum preço gravado para {dia:%d/%m/%Y}. "
                "Rode `manage.py puxar_precos` antes."
            )

        taxa_cdi = adapters.taxa_cdi_do_dia(dia)

        for fundo in models.Fundo.objects.filter(ativo=True):
            self._apurar(fundo, dia, precos, cambios, taxa_cdi, refazer)

    @transaction.atomic
    def _apurar(self, fundo, dia, precos, cambios, taxa_cdi, refazer):
        if fundo.inicio > dia:
            return

        ja_apurado = models.Fechamento.objects.filter(fundo=fundo, data=dia).exists()
        if ja_apurado and not refazer:
            self.stdout.write(f"{fundo}: já apurado em {dia}. Pulando.")
            return

        if refazer:
            # O aluguel do dia também sai, senão a reapuração cobraria duas vezes.
            models.Fechamento.objects.filter(fundo=fundo, data=dia).delete()
            models.Lancamento.objects.filter(
                fundo=fundo,
                executado_em=dia,
                tipo=models.Lancamento.Tipo.ALUGUEL_SHORT,
            ).delete()

        fundo_core = adapters.para_core_fundo(fundo)
        eventos = adapters.eventos_do_fundo(fundo, ate=dia)

        try:
            fechamento, aluguel = engine.apurar_dia(
                fundo_core, eventos, precos, cambios, taxa_cdi, dia
            )
        except KeyError as erro:
            # Faltou preço de um ativo que o fundo carrega: não dá para marcar a
            # carteira. Melhor não apurar do que apurar errado.
            raise CommandError(f"{fundo}: {erro}") from erro

        # O lançamento precisa ser persistido junto — se ficar de fora, o custo
        # daquele dia desaparece do ledger para sempre.
        if aluguel is not None:
            models.Lancamento.objects.create(
                fundo=fundo,
                tipo=aluguel.tipo.value,
                valor=aluguel.valor.quantize(engine.CENTAVO),
                executado_em=aluguel.executado_em,
                descricao=aluguel.descricao,
            )

        models.Fechamento.objects.create(
            fundo=fundo,
            data=dia,
            caixa=fechamento.caixa,
            valor_posicoes=fechamento.valor_posicoes,
            patrimonio=fechamento.patrimonio,
            cota=fechamento.cota,
        )

        custo = f" | aluguel {aluguel.valor:.2f}" if aluguel else ""
        self.stdout.write(
            self.style.SUCCESS(f"{fundo}: cota {fechamento.cota}{custo}")
        )


def _resolver_data(texto: str | None) -> date:
    if not texto:
        return date.today()
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as erro:
        raise CommandError("Data inválida. Use AAAA-MM-DD.") from erro
