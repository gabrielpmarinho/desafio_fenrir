"""Telas do participante.

Toda view exige login e resolve o fundo a partir do usuário — nunca de um
parâmetro da URL. Assim um gestor não consegue ver nem operar a carteira de
outro fundo trocando o endereço.
"""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OrdemForm, janela_aberta
from .models import Ordem
from .servicos import carteira


def _fundo_do(request):
    participante = getattr(request.user, "participante", None)
    if participante is None:
        raise Http404(
            "Seu usuário não está vinculado a nenhum fundo. Fale com a diretoria."
        )
    return participante.fundo


@login_required
def dashboard(request):
    fundo = _fundo_do(request)
    return render(
        request,
        "desafio/dashboard.html",
        {
            "fundo": fundo,
            "visao": carteira.visao(fundo),
            "avisos": carteira.avisos_vigentes(),
            "ultimos": carteira.ultimos_fechamentos(fundo),
            "comparado": json.dumps(carteira.serie_comparada(fundo)),
        },
    )


@login_required
def ordens(request):
    fundo = _fundo_do(request)

    if request.method == "POST":
        formulario = OrdemForm(request.POST)
        if formulario.is_valid():
            ordem = formulario.save(commit=False)
            ordem.fundo = fundo
            ordem.enviada_por = request.user
            ordem.save()
            messages.success(
                request,
                f"Boleta registrada: {ordem.get_direcao_display()} de "
                f"{ordem.quantidade} {ordem.ticker}. Será liquidada na segunda, "
                "ao preço de fechamento.",
            )
            return redirect("ordens")
    else:
        formulario = OrdemForm()

    return render(
        request,
        "desafio/ordens.html",
        {
            "fundo": fundo,
            "form": formulario,
            "janela_aberta": janela_aberta(),
            "ordens": fundo.ordens.order_by("-enviada_em")[:50],
            "pendentes": fundo.ordens.filter(status=Ordem.Status.PENDENTE).count(),
        },
    )


@login_required
def cancelar_ordem(request, ordem_id):
    """Cancela boleta ainda não liquidada. Só POST, só do próprio fundo.

    O fundo e o status entram no filtro do get_object_or_404, não numa
    comparação depois: ordem de outro fundo, ou já executada, é 404 — e um POST
    repetido não "cancela de novo".
    """
    if request.method != "POST":
        raise Http404("Cancelamento só por POST.")

    fundo = _fundo_do(request)
    ordem = get_object_or_404(
        Ordem, id=ordem_id, fundo=fundo, status=Ordem.Status.PENDENTE
    )
    ordem.status = Ordem.Status.CANCELADA
    ordem.save(update_fields=["status"])
    messages.success(
        request,
        f"Boleta cancelada: {ordem.get_direcao_display()} de "
        f"{ordem.quantidade} {ordem.ticker}.",
    )
    return redirect("ordens")


@login_required
def ranking(request):
    fundo = _fundo_do(request)
    return render(
        request,
        "desafio/ranking.html",
        {
            "fundo": fundo,
            "linhas": carteira.ranking(),
            "data_ranking": carteira.data_do_ranking(),
            "grafico": json.dumps(carteira.serie_semanal_dos_fundos()),
        },
    )


@login_required
def extrato(request):
    """Ledger do fundo: trades e lançamentos, incluindo o aluguel de short."""
    fundo = _fundo_do(request)
    return render(
        request,
        "desafio/extrato.html",
        {
            "fundo": fundo,
            "trades": fundo.trades.order_by("-executado_em", "-id")[:100],
            "lancamentos": fundo.lancamentos.order_by("-executado_em", "-id")[:100],
        },
    )
