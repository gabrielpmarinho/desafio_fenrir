"""Liquidação das ordens da semana.

Roda na segunda-feira, depois do `puxar_precos` da própria segunda. As boletas
pendentes são processadas na ordem de chegada, ao preço de fechamento do dia
(regulamento §4.1).
"""

from __future__ import annotations

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import engine
from core.calendario import eh_dia_util
from core.models import Direcao, Ordem as OrdemCore, Rejeicao
from core.universo import UNIVERSO
from desafio import adapters, models


class Command(BaseCommand):
    help = "Liquida as ordens pendentes ao preço de fechamento do dia."

    def add_arguments(self, parser):
        parser.add_argument("--data", help="Data AAAA-MM-DD. Padrão: hoje.")
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Mostra o que aconteceria sem gravar nada.",
        )

    def handle(self, *args, **opcoes):
        dia = _resolver_data(opcoes.get("data"))
        simular = opcoes["simular"]

        if not eh_dia_util(dia):
            raise CommandError(f"{dia} não é dia útil — não há preço de fechamento.")

        pendentes = list(
            models.Ordem.objects.filter(status=models.Ordem.Status.PENDENTE)
            .select_related("fundo")
            .order_by("enviada_em")
        )
        if not pendentes:
            self.stdout.write("Nenhuma ordem pendente. Mesa limpa.")
            return

        try:
            precos, cambios = adapters.precos_do_dia(dia)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        if not precos:
            raise CommandError(
                f"Sem preços para {dia:%d/%m/%Y}. Rode `manage.py puxar_precos` antes."
            )

        taxa_cdi = adapters.taxa_cdi_do_dia(dia)

        # Cada fundo é liquidado isoladamente: o limite de exposição é por fundo,
        # e uma rejeição num fundo não pode contaminar outro.
        for fundo in {o.fundo for o in pendentes}:
            do_fundo = [o for o in pendentes if o.fundo_id == fundo.id]
            self._liquidar_fundo(
                fundo, do_fundo, dia, precos, cambios, taxa_cdi, simular
            )

    @transaction.atomic
    def _liquidar_fundo(self, fundo, ordens, dia, precos, cambios, taxa_cdi, simular):
        fundo_core = adapters.para_core_fundo(fundo)
        ledger = adapters.eventos_do_fundo(fundo, ate=dia)

        # A boleta do motor guarda o id do registro no Django, para o resultado
        # voltar colado na linha certa do banco.
        registros = {}
        boletas = []
        for registro in ordens:
            boleta = OrdemCore(
                fundo=fundo.nome,
                ticker=registro.ticker,
                quantidade=registro.quantidade,
                direcao=Direcao(registro.direcao),
                enviada_em=registro.enviada_em,
            )
            boletas.append(boleta)
            registros[id(boleta)] = registro

        resultados = engine.executar_lote(
            boletas,
            {fundo.nome: fundo_core},
            ledger,
            UNIVERSO,
            precos,
            cambios,
            taxa_cdi,
            dia,
        )

        for boleta, resultado in resultados:
            registro = registros[id(boleta)]
            if isinstance(resultado, Rejeicao):
                self._rejeitar(registro, resultado, simular)
            else:
                self._executar(registro, resultado, dia, simular)

    def _executar(self, registro, trade_core, dia, simular):
        rotulo = f"{registro.fundo}: {registro.direcao} {registro.quantidade} {registro.ticker}"
        if simular:
            self.stdout.write(f"[simulação] EXECUTA {rotulo} @ {trade_core.preco_nativo}")
            return

        trade = models.Trade.objects.create(
            fundo=registro.fundo,
            ordem=registro,
            ticker=trade_core.ticker,
            quantidade=trade_core.quantidade,
            preco_nativo=trade_core.preco_nativo,
            cambio=trade_core.cambio,
            executado_em=dia,
        )
        registro.status = models.Ordem.Status.EXECUTADA
        registro.save(update_fields=["status"])
        self.stdout.write(self.style.SUCCESS(f"EXECUTADA {rotulo} @ {trade.preco_nativo}"))

    def _rejeitar(self, registro, rejeicao: Rejeicao, simular):
        rotulo = f"{registro.fundo}: {registro.direcao} {registro.quantidade} {registro.ticker}"
        if simular:
            self.stdout.write(f"[simulação] REJEITA {rotulo} — {rejeicao.motivo}")
            return

        registro.status = models.Ordem.Status.REJEITADA
        registro.motivo_rejeicao = rejeicao.motivo
        registro.save(update_fields=["status", "motivo_rejeicao"])
        self.stdout.write(self.style.WARNING(f"REJEITADA {rotulo} — {rejeicao.motivo}"))


def _resolver_data(texto: str | None) -> date:
    if not texto:
        return date.today()
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as erro:
        raise CommandError("Data inválida. Use AAAA-MM-DD.") from erro
