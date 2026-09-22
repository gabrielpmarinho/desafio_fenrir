"""Popula o banco local com uma edição fictícia do desafio.

Serve para ver as telas com conteúdo de verdade — gráfico com histórico,
carteira com posições, extrato com aluguel — sem esperar semanas de competição.

Só roda com DEBUG=True. Nunca em produção.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.calendario import eh_dia_util
from core.universo import UNIVERSO
from desafio import models

FUNDOS = ["Astra Capital", "Bridgewater Capital", "Citadel Capital", "Renaissance Capital"]

PRECO_BASE = {
    "SPY": 500, "QQQ": 430, "BOVA11.SA": 130, "MCHI": 50, "TLT": 90, "USO": 75,
    "GLD": 200, "IMAB11.SA": 100, "XFIX11.SA": 9, "VNQ": 90, "XLV": 145,
    "IBIT": 60, "NLR": 90, "BOTZ": 35, "PAVE": 42, "XLK": 220, "XLF": 45,
    "PETR4.SA": 38, "VALE3.SA": 62, "ITUB4.SA": 34, "BBAS3.SA": 27,
    "WEGE3.SA": 52, "ELET3.SA": 41, "RENT3.SA": 45, "RADL3.SA": 26,
    "SUZB3.SA": 58, "JBSS3.SA": 33, "B3SA3.SA": 12, "ABEV3.SA": 13, "MGLU3.SA": 9,
}

# Uma carteira diferente por fundo, para o gráfico não sair com quatro linhas iguais.
CARTEIRAS = {
    # A Astra é o fundo do usuário da demo: leva uma perna vendida para o
    # extrato mostrar o aluguel de short dia a dia.
    "Astra Capital": [
        ("PETR4.SA", 800_000, "COMPRA"),
        ("GLD", 30_000, "COMPRA"),
        ("MGLU3.SA", 900_000, "VENDA"),
    ],
    "Bridgewater Capital": [("SPY", 60_000, "COMPRA"), ("TLT", 50_000, "COMPRA")],
    "Citadel Capital": [("VALE3.SA", 500_000, "COMPRA"), ("MGLU3.SA", 900_000, "VENDA")],
    "Renaissance Capital": [("XLK", 90_000, "COMPRA"), ("IBIT", 120_000, "COMPRA")],
}


class Command(BaseCommand):
    help = "Cria uma edição de demonstração com histórico de cotas (só em DEBUG)."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", default="gabriel")
        parser.add_argument("--senha", default="fenrir")
        parser.add_argument("--dias", type=int, default=20, help="Dias úteis de histórico.")
        parser.add_argument("--limpar", action="store_true", help="Apaga a demo antes.")

    def handle(self, *args, **opcoes):
        if not settings.DEBUG:
            raise CommandError("semear_demo só roda com DEBUG=True.")

        if opcoes["limpar"]:
            self._limpar()

        random.seed(42)  # histórico reproduzível
        dias = self._dias_uteis(opcoes["dias"])
        inicio = dias[0]

        self._precos(dias)
        self.stdout.write(f"Preços gravados para {len(dias)} dias úteis.")

        fundos = self._fundos(inicio)
        usuario = self._usuario(opcoes["usuario"], opcoes["senha"], fundos[0])

        self._boletas(fundos)
        call_command("liquidar_semana", data=inicio.isoformat(), stdout=self.stdout)

        for dia in dias:
            call_command("fechar_dia", data=dia.isoformat(), stdout=self.stdout)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nPronto. Entre em http://127.0.0.1:8000/ como "
                f"'{usuario.username}' / '{opcoes['senha']}' "
                f"(gerindo {fundos[0].nome})."
            )
        )

    # -- partes ----------------------------------------------------------
    def _limpar(self):
        models.Fechamento.objects.all().delete()
        models.Lancamento.objects.all().delete()
        models.Trade.objects.all().delete()
        models.Ordem.objects.all().delete()
        models.Participante.objects.all().delete()
        models.Fundo.objects.all().delete()
        models.PrecoFechamento.objects.all().delete()
        models.Benchmark.objects.all().delete()
        models.Cotacao.objects.all().delete()
        models.TaxaCDI.objects.all().delete()
        self.stdout.write(self.style.WARNING("Demo anterior apagada."))

    def _dias_uteis(self, quantidade: int) -> list[date]:
        dias: list[date] = []
        cursor = date.today()
        while len(dias) < quantidade:
            if eh_dia_util(cursor):
                dias.append(cursor)
            cursor -= timedelta(days=1)
        return sorted(dias)

    def _precos(self, dias: list[date]):
        precos = {t: float(PRECO_BASE.get(t, 50)) for t in UNIVERSO}
        indices = {"IBOV": 186_000.0, "SP500": 7_580.0}
        cambio = 5.40

        for dia in dias:
            for ticker in UNIVERSO:
                # Passeio aleatório suave: ~1,2% de desvio diário.
                precos[ticker] *= 1 + random.gauss(0.0004, 0.012)
                models.PrecoFechamento.objects.update_or_create(
                    ticker=ticker,
                    data=dia,
                    defaults={"preco": Decimal(f"{precos[ticker]:.8f}")},
                )

            for codigo, valor in indices.items():
                indices[codigo] = valor * (1 + random.gauss(0.0003, 0.011))
                models.Benchmark.objects.update_or_create(
                    codigo=codigo,
                    data=dia,
                    defaults={"valor": Decimal(f"{indices[codigo]:.8f}")},
                )

            cambio *= 1 + random.gauss(0, 0.005)
            models.Cotacao.objects.update_or_create(
                data=dia, defaults={"usd_brl": Decimal(f"{cambio:.8f}")}
            )
            models.TaxaCDI.objects.update_or_create(
                data=dia, defaults={"taxa_diaria": Decimal("0.0005")}
            )

    def _fundos(self, inicio: date) -> list[models.Fundo]:
        criados = []
        for nome in FUNDOS:
            fundo, _ = models.Fundo.objects.get_or_create(
                nome=nome,
                defaults={
                    "slug": nome.lower().replace(" ", "-"),
                    "inicio": inicio,
                },
            )
            criados.append(fundo)
        return criados

    def _usuario(self, login: str, senha: str, fundo: models.Fundo) -> User:
        usuario, novo = User.objects.get_or_create(
            username=login, defaults={"is_staff": True, "is_superuser": True}
        )
        if novo:
            usuario.set_password(senha)
            usuario.save()
        models.Participante.objects.get_or_create(
            usuario=usuario, defaults={"fundo": fundo, "nucleo": "MACRO"}
        )
        return usuario

    def _boletas(self, fundos: list[models.Fundo]):
        for fundo in fundos:
            for ticker, quantidade, direcao in CARTEIRAS[fundo.nome]:
                models.Ordem.objects.get_or_create(
                    fundo=fundo,
                    ticker=ticker,
                    quantidade=quantidade,
                    direcao=direcao,
                    status=models.Ordem.Status.PENDENTE,
                )
