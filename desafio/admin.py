"""Mesa de Operações.

O que na versão antiga era um painel escrito à mão, com botão de "liquidar tudo"
que mutava planilha, aqui é o admin do Django sobre um ledger append-only.

Trade e Lançamento são **somente leitura** depois de criados: o histórico do
desafio não se edita. Para corrigir, lance um ajuste contrário.
"""

from __future__ import annotations

from django.contrib import admin

from . import models


@admin.register(models.Fundo)
class FundoAdmin(admin.ModelAdmin):
    list_display = ("nome", "inicio", "caixa_inicial", "cotas_emitidas", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(models.Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ("usuario", "fundo", "nucleo")
    list_filter = ("fundo", "nucleo")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__email")
    autocomplete_fields = ("fundo",)


@admin.register(models.Ordem)
class OrdemAdmin(admin.ModelAdmin):
    list_display = (
        "enviada_em", "fundo", "direcao", "quantidade", "ticker", "status",
    )
    list_filter = ("status", "direcao", "fundo")
    search_fields = ("ticker", "fundo__nome")
    date_hierarchy = "enviada_em"
    readonly_fields = ("enviada_em", "enviada_por", "status", "motivo_rejeicao")

    def has_change_permission(self, request, obj=None):
        # Boleta enviada não se edita; quem decide o destino dela é a Mesa.
        return False


class SomenteLeituraNoLedger(admin.ModelAdmin):
    """Deixa criar (ajuste manual) e ver, nunca editar nem apagar."""

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Trade)
class TradeAdmin(SomenteLeituraNoLedger):
    list_display = (
        "executado_em", "fundo", "ticker", "quantidade", "preco_nativo", "cambio",
    )
    list_filter = ("fundo", "ticker")
    search_fields = ("ticker", "fundo__nome")
    date_hierarchy = "executado_em"
    autocomplete_fields = ("fundo",)


@admin.register(models.Lancamento)
class LancamentoAdmin(SomenteLeituraNoLedger):
    list_display = ("executado_em", "fundo", "tipo", "valor", "descricao")
    list_filter = ("tipo", "fundo")
    date_hierarchy = "executado_em"
    autocomplete_fields = ("fundo",)


@admin.register(models.Fechamento)
class FechamentoAdmin(admin.ModelAdmin):
    list_display = ("data", "fundo", "cota", "patrimonio", "caixa", "valor_posicoes")
    list_filter = ("fundo",)
    date_hierarchy = "data"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        # Fechamento nasce do comando `fechar_dia`, nunca digitado à mão.
        return False


@admin.register(models.PrecoFechamento)
class PrecoFechamentoAdmin(admin.ModelAdmin):
    list_display = ("data", "ticker", "preco")
    list_filter = ("ticker",)
    search_fields = ("ticker",)
    date_hierarchy = "data"


@admin.register(models.Cotacao)
class CotacaoAdmin(admin.ModelAdmin):
    list_display = ("data", "usd_brl")
    date_hierarchy = "data"


@admin.register(models.TaxaCDI)
class TaxaCDIAdmin(admin.ModelAdmin):
    list_display = ("data", "taxa_diaria")
    date_hierarchy = "data"


@admin.register(models.Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = ("data", "codigo", "valor")
    list_filter = ("codigo",)
    date_hierarchy = "data"


@admin.register(models.Aviso)
class AvisoAdmin(admin.ModelAdmin):
    """Mural da Diretoria. Ao contrário do ledger, aviso se edita e se apaga."""

    list_display = ("titulo", "ativo", "vigente_ate", "criado_em", "criado_por")
    list_filter = ("ativo",)
    search_fields = ("titulo", "mensagem")
    readonly_fields = ("criado_em", "criado_por")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


admin.site.site_header = "Terminal Fenrir — Mesa de Operações"
admin.site.site_title = "Fenrir"
admin.site.index_title = "Administração do Desafio"
