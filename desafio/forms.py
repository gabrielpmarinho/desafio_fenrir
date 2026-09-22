"""Formulário de envio de boleta."""

from __future__ import annotations

from datetime import date

from django import forms

from core.universo import ACOES_B3, ETFS

from .models import Ordem

# Fim de semana: sábado e domingo (regulamento §4).
DIAS_DE_JANELA = (5, 6)


def janela_aberta(dia: date | None = None) -> bool:
    """O envio de ordens só acontece aos finais de semana."""
    return (dia or date.today()).weekday() in DIAS_DE_JANELA


class OrdemForm(forms.ModelForm):
    ticker = forms.ChoiceField(
        label="Ativo",
        choices=[
            ("ETFs", [(a.ticker, f"{a.ticker} — {a.nome}") for a in ETFS]),
            ("Ações B3", [(a.ticker, f"{a.ticker} — {a.nome}") for a in ACOES_B3]),
        ],
    )

    class Meta:
        model = Ordem
        fields = ["ticker", "direcao", "quantidade"]
        labels = {"direcao": "Operação", "quantidade": "Quantidade"}
        widgets = {
            "quantidade": forms.NumberInput(attrs={"min": 1, "step": 1}),
        }

    def clean_quantidade(self):
        quantidade = self.cleaned_data["quantidade"]
        if quantidade < 1:
            raise forms.ValidationError("A quantidade tem que ser pelo menos 1.")
        return quantidade

    def clean(self):
        # A janela é revalidada aqui, e não só na view: formulário que confia em
        # checagem de tela aceita POST fora de hora.
        if not janela_aberta():
            raise forms.ValidationError(
                "A janela de envio está fechada. Ordens são aceitas apenas aos "
                "finais de semana (regulamento §4)."
            )
        return super().clean()
