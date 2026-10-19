"""Cópia do banco SQLite, para rodar logo depois da rotina diária.

O banco guarda o ledger e as cotas: perdido, a competição se perde junto. A
cópia usa a API de backup do próprio SQLite, que é consistente mesmo com o
site no ar — copiar o arquivo direto pode pegar uma escrita pela metade.

Com Postgres (DATABASE_URL), o backup é do provedor ou do `pg_dump`; este
comando recusa em vez de fingir que copiou.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Copia o banco SQLite para backups/ e mantém só as cópias mais recentes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--destino",
            default=str(settings.BASE_DIR / "backups"),
            help="Pasta das cópias. Padrão: backups/ na raiz do projeto.",
        )
        parser.add_argument(
            "--manter",
            type=int,
            default=14,
            help="Quantas cópias guardar (as mais antigas são apagadas). Padrão: 14.",
        )

    def handle(self, *args, **opcoes):
        if connection.vendor != "sqlite":
            raise CommandError(
                f"Banco {connection.vendor}: use o backup do provedor ou `pg_dump`."
            )
        if opcoes["manter"] < 1:
            raise CommandError("--manter precisa ser pelo menos 1.")

        destino = Path(opcoes["destino"])
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f"fenrir_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"

        connection.ensure_connection()
        copia = sqlite3.connect(arquivo)
        try:
            connection.connection.backup(copia)
        finally:
            copia.close()
        self.stdout.write(self.style.SUCCESS(f"Backup gravado em {arquivo}"))

        antigas = sorted(destino.glob("fenrir_*.sqlite3"))[: -opcoes["manter"]]
        for velha in antigas:
            velha.unlink()
        if antigas:
            self.stdout.write(f"{len(antigas)} cópia(s) antiga(s) apagada(s).")
