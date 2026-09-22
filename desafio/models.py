"""Tabelas do Terminal Fenrir.

Espelham os tipos de `core/`. A regra: estes modelos só **guardam** — quem
calcula é o motor. Nenhuma conta de caixa, posição ou cota mora aqui.

Ledger append-only: `Trade` e `Lancamento` nunca são editados nem apagados
depois de criados. Erro de liquidação se corrige com lançamento contrário.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

DINHEIRO = {"max_digits": 20, "decimal_places": 2}
PRECO = {"max_digits": 20, "decimal_places": 8}


class Fundo(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    caixa_inicial = models.DecimalField(**DINHEIRO, default=Decimal("100000000.00"))
    cotas_emitidas = models.DecimalField(**DINHEIRO, default=Decimal("1000000.00"))
    inicio = models.DateField(help_text="Primeiro dia de rentabilidade do fundo.")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "fundos"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Participante(models.Model):
    """Liga um usuário do Django ao fundo que ele gere."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participante"
    )
    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name="membros")
    nucleo = models.CharField(
        max_length=40,
        choices=[
            ("MACRO", "Macro & Data Science"),
            ("RISCO", "Risco & Backoffice"),
            ("EQUITY", "Equity Research"),
        ],
    )

    def __str__(self) -> str:
        return f"{self.usuario} — {self.fundo}"


class Ordem(models.Model):
    """Boleta enviada por um fundo. Vira Trade quando a Mesa liquida."""

    class Direcao(models.TextChoices):
        COMPRA = "COMPRA", "Compra"
        VENDA = "VENDA", "Venda"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EXECUTADA = "EXECUTADA", "Executada"
        REJEITADA = "REJEITADA", "Rejeitada"
        CANCELADA = "CANCELADA", "Cancelada"

    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name="ordens")
    ticker = models.CharField(max_length=20)
    quantidade = models.PositiveIntegerField()
    direcao = models.CharField(max_length=10, choices=Direcao.choices)
    enviada_em = models.DateTimeField(auto_now_add=True)
    enviada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    motivo_rejeicao = models.TextField(blank=True)

    class Meta:
        ordering = ["enviada_em"]

    def __str__(self) -> str:
        return f"{self.fundo} {self.direcao} {self.quantidade} {self.ticker}"


class Trade(models.Model):
    """Ordem executada. Linha imutável do ledger.

    `quantidade` é assinada: positiva compra, negativa venda.
    """

    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name="trades")
    ordem = models.OneToOneField(
        Ordem, on_delete=models.PROTECT, null=True, blank=True, related_name="trade"
    )
    ticker = models.CharField(max_length=20)
    quantidade = models.BigIntegerField()
    preco_nativo = models.DecimalField(**PRECO)
    cambio = models.DecimalField(**PRECO, default=Decimal("1"))
    executado_em = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["executado_em", "id"]

    def __str__(self) -> str:
        return f"{self.fundo} {self.quantidade:+} {self.ticker} @ {self.preco_nativo}"


class Lancamento(models.Model):
    """Movimento de caixa sem trade — aluguel de short, ajuste da mesa."""

    class Tipo(models.TextChoices):
        ALUGUEL_SHORT = "ALUGUEL_SHORT", "Aluguel de short"
        AJUSTE = "AJUSTE", "Ajuste da mesa"

    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name="lancamentos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    valor = models.DecimalField(**DINHEIRO, help_text="Negativo debita o caixa.")
    executado_em = models.DateField()
    descricao = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["executado_em", "id"]
        constraints = [
            # Um fundo só paga aluguel uma vez por dia. Trava no banco a dupla
            # execução do fechamento, que cobraria o custo duas vezes.
            models.UniqueConstraint(
                fields=["fundo", "executado_em"],
                condition=models.Q(tipo="ALUGUEL_SHORT"),
                name="aluguel_unico_por_dia",
            )
        ]

    def __str__(self) -> str:
        return f"{self.fundo} {self.tipo} {self.valor}"


class PrecoFechamento(models.Model):
    """Preço de fechamento persistido.

    O histórico do desafio nunca pode depender de uma chamada ao vivo: o preço
    usado numa apuração fica gravado como ele era naquele dia.
    """

    ticker = models.CharField(max_length=20)
    data = models.DateField()
    preco = models.DecimalField(**PRECO)

    class Meta:
        unique_together = [("ticker", "data")]
        ordering = ["-data", "ticker"]
        verbose_name = "preço de fechamento"
        verbose_name_plural = "preços de fechamento"

    def __str__(self) -> str:
        return f"{self.ticker} {self.data} {self.preco}"


class Cotacao(models.Model):
    """USD/BRL de fechamento do dia."""

    data = models.DateField(unique=True)
    usd_brl = models.DecimalField(**PRECO)

    class Meta:
        ordering = ["-data"]
        verbose_name = "cotação USD/BRL"
        verbose_name_plural = "cotações USD/BRL"

    def __str__(self) -> str:
        return f"USDBRL {self.data} {self.usd_brl}"


class TaxaCDI(models.Model):
    """CDI diário do BCB (série 12), guardado para a apuração ser reproduzível."""

    data = models.DateField(unique=True)
    taxa_diaria = models.DecimalField(max_digits=12, decimal_places=10)

    class Meta:
        ordering = ["-data"]
        verbose_name = "taxa CDI"
        verbose_name_plural = "taxas CDI"

    def __str__(self) -> str:
        return f"CDI {self.data} {self.taxa_diaria}"


class Fechamento(models.Model):
    """Foto imutável de um fundo num dia. Fonte do ranking e das métricas."""

    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name="fechamentos")
    data = models.DateField()
    caixa = models.DecimalField(**DINHEIRO)
    valor_posicoes = models.DecimalField(**DINHEIRO)
    patrimonio = models.DecimalField(**DINHEIRO)
    cota = models.DecimalField(**DINHEIRO)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("fundo", "data")]
        ordering = ["-data", "fundo"]

    def __str__(self) -> str:
        return f"{self.fundo} {self.data} cota {self.cota}"


class Aviso(models.Model):
    """Recado do Diretor de Competições, exibido na carteira de todos os fundos.

    Não é ledger: aviso se corrige e se apaga. O que o histórico guarda é o
    resultado do desafio, não o mural.
    """

    titulo = models.CharField(max_length=140)
    mensagem = models.TextField()
    ativo = models.BooleanField(default=True)
    vigente_ate = models.DateField(
        null=True,
        blank=True,
        help_text="Último dia em que o aviso aparece. Em branco, fica até ser desativado.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "aviso"
        verbose_name_plural = "avisos"

    def __str__(self) -> str:
        return self.titulo


class Benchmark(models.Model):
    """Fechamento de um índice de referência (IBOV, S&P) para o gráfico.

    Tabela separada de `PrecoFechamento` de propósito: índice não é ativo
    investível. Misturar os dois faria o dicionário de preços da apuração
    carregar papel que nenhum fundo pode ter em carteira.
    """

    class Codigo(models.TextChoices):
        IBOV = "IBOV", "Ibovespa"
        SP500 = "SP500", "S&P 500"

    codigo = models.CharField(max_length=10, choices=Codigo.choices)
    data = models.DateField()
    valor = models.DecimalField(**PRECO)

    class Meta:
        unique_together = [("codigo", "data")]
        ordering = ["-data", "codigo"]
        verbose_name = "benchmark"
        verbose_name_plural = "benchmarks"

    def __str__(self) -> str:
        return f"{self.codigo} {self.data} {self.valor}"
