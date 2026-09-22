"""Visão da carteira para as telas do participante.

Consulta, nunca escreve. Toda conta vem do motor; aqui só se busca o que ele
precisa e se formata o resultado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q

from core import engine
from core.calendario import eh_dia_util, ultimo_dia_util_da_semana
from core.universo import UNIVERSO

from .. import adapters, models

COTA_BASE = Decimal("100")


@dataclass(frozen=True)
class LinhaPosicao:
    ticker: str
    nome: str
    quantidade: int
    preco: Decimal
    preco_brl: Decimal
    valor: Decimal

    @property
    def vendida(self) -> bool:
        return self.quantidade < 0

    @property
    def estrangeira(self) -> bool:
        return UNIVERSO[self.ticker].estrangeiro if self.ticker in UNIVERSO else False


@dataclass(frozen=True)
class VisaoCarteira:
    fundo: models.Fundo
    data: date | None
    caixa: Decimal
    valor_posicoes: Decimal
    patrimonio: Decimal
    cota: Decimal
    rentabilidade: Decimal
    posicoes: list[LinhaPosicao]
    exposicao_bruta: Decimal

    @property
    def apurada(self) -> bool:
        """False quando o desafio ainda não teve nenhum fechamento."""
        return self.data is not None


def ultima_data_com_preco() -> date | None:
    ultimo = models.PrecoFechamento.objects.order_by("-data").first()
    return ultimo.data if ultimo else None


def visao(fundo: models.Fundo) -> VisaoCarteira:
    """Estado do fundo no último fechamento apurado.

    Se ainda não houve apuração, devolve a posição de partida — caixa cheio,
    cota 100 — para a tela não quebrar no primeiro dia.
    """
    fechamento = fundo.fechamentos.order_by("-data").first()
    dia = fechamento.data if fechamento else ultima_data_com_preco()

    if dia is None:
        return VisaoCarteira(
            fundo=fundo,
            data=None,
            caixa=fundo.caixa_inicial,
            valor_posicoes=Decimal("0.00"),
            patrimonio=fundo.caixa_inicial,
            cota=COTA_BASE,
            rentabilidade=Decimal("0.00"),
            posicoes=[],
            exposicao_bruta=Decimal("0.00"),
        )

    precos, cambios = adapters.precos_do_dia(dia)
    posicoes = engine.posicoes(adapters.eventos_do_fundo(fundo, ate=dia), ate=dia)

    linhas = []
    for ticker, quantidade in sorted(posicoes.items()):
        preco = precos.get(ticker)
        if preco is None:
            continue
        cambio = cambios.get(ticker, Decimal("1"))
        preco_brl = preco * cambio
        linhas.append(
            LinhaPosicao(
                ticker=ticker,
                nome=UNIVERSO[ticker].nome if ticker in UNIVERSO else ticker,
                quantidade=quantidade,
                preco=preco,
                preco_brl=preco_brl,
                valor=Decimal(quantidade) * preco_brl,
            )
        )

    if fechamento is not None:
        caixa = fechamento.caixa
        valor_posicoes = fechamento.valor_posicoes
        patrimonio = fechamento.patrimonio
        cota = fechamento.cota
    else:
        # Há preço mas o fechamento do dia ainda não rodou.
        fundo_core = adapters.para_core_fundo(fundo)
        eventos = adapters.eventos_do_fundo(fundo, ate=dia)
        taxa = adapters.taxa_cdi_do_dia(dia)
        parcial = engine.fechar(fundo_core, eventos, precos, cambios, taxa, dia)
        caixa, valor_posicoes = parcial.caixa, parcial.valor_posicoes
        patrimonio, cota = parcial.patrimonio, parcial.cota

    return VisaoCarteira(
        fundo=fundo,
        data=dia,
        caixa=caixa,
        valor_posicoes=valor_posicoes,
        patrimonio=patrimonio,
        cota=cota,
        rentabilidade=(cota / COTA_BASE - 1) * 100,
        posicoes=linhas,
        exposicao_bruta=engine.exposicao_bruta(posicoes, precos, cambios),
    )


def serie_de_cotas() -> dict[str, list]:
    """Série de todos os fundos para o gráfico do ranking."""
    fechamentos = models.Fechamento.objects.select_related("fundo").order_by("data")

    datas: list[str] = []
    por_fundo: dict[str, dict[str, float]] = {}
    for f in fechamentos:
        rotulo = f.data.strftime("%d/%m")
        if rotulo not in datas:
            datas.append(rotulo)
        por_fundo.setdefault(f.fundo.nome, {})[rotulo] = float(f.cota)

    return {
        "datas": datas,
        "series": [
            {"nome": nome, "cotas": [pontos.get(d) for d in datas]}
            for nome, pontos in sorted(por_fundo.items())
        ],
    }


def data_do_ranking(hoje: date | None = None) -> date | None:
    """Data da foto semanal: o último fechamento até o fim da semana passada.

    O ranking congela na sexta de propósito (decisão do Gabriel, 21/09/2026):
    saber a cota alheia não ajuda a montar carteira, muda postura — e para isso
    não precisa ser diário. A cota do próprio fundo continua diária.
    """
    alvo = ultimo_dia_util_da_semana(hoje or date.today())
    datas = models.Fechamento.objects.order_by("-data").values_list("data", flat=True)

    fechada = datas.filter(data__lte=alvo).first()
    if fechada is not None:
        return fechada

    # Nenhuma semana fechou ainda (primeiros dias do desafio): mostra a apuração
    # mais recente em vez de deixar a tela vazia até a primeira sexta.
    return datas.first()


def ranking(hoje: date | None = None) -> list[models.Fechamento]:
    """Fechamento semanal de cada fundo, do melhor para o pior."""
    data = data_do_ranking(hoje)
    if data is None:
        return []
    return list(
        models.Fechamento.objects.filter(data=data)
        .select_related("fundo")
        .order_by("-cota")
    )


def serie_semanal_dos_fundos(hoje: date | None = None) -> dict[str, list]:
    """Uma cota por semana, por fundo, para a comparação entre grupos.

    Pega o último fechamento de cada semana — não exige que a sexta tenha sido
    apurada, senão uma semana inteira sumiria do gráfico por um feriado. A
    semana corrente fica de fora: o gráfico congela junto com o ranking, senão
    ele viraria a espiada diária na cota alheia que a regra quer evitar.
    """
    limite = ultimo_dia_util_da_semana(hoje or date.today())
    fechamentos = models.Fechamento.objects.select_related("fundo").order_by("data")

    por_semana: dict[tuple[str, date], models.Fechamento] = {}
    for f in fechamentos:
        semana = ultimo_dia_util_da_semana(f.data + timedelta(days=6 - f.data.weekday()))
        if semana > limite:
            continue
        chave = (f.fundo.nome, semana)
        if chave not in por_semana or f.data > por_semana[chave].data:
            por_semana[chave] = f

    if not por_semana:  # nenhuma semana fechou ainda
        return {"datas": [], "series": []}

    semanas = sorted({semana for _, semana in por_semana})
    nomes = sorted({nome for nome, _ in por_semana})

    # O rótulo é a data do fechamento que de fato entrou, não a sexta teórica:
    # numa semana sem apuração na sexta, dizer "18/09" com número de segunda mente.
    rotulos = {
        semana: max(
            f.data for (_, s), f in por_semana.items() if s == semana
        ).strftime("%d/%m")
        for semana in semanas
    }

    return {
        "datas": [rotulos[s] for s in semanas],
        "series": [
            {
                "nome": nome,
                "cotas": [
                    float(por_semana[(nome, s)].cota) if (nome, s) in por_semana else None
                    for s in semanas
                ],
            }
            for nome in nomes
        ],
    }


def avisos_vigentes():
    """Mural da Diretoria: ativos e ainda dentro da validade."""
    hoje = date.today()
    return models.Aviso.objects.filter(ativo=True).filter(
        Q(vigente_ate__isnull=True) | Q(vigente_ate__gte=hoje)
    )[:5]


@dataclass(frozen=True)
class LinhaCota:
    data: date
    cota: Decimal
    variacao: Decimal | None


def ultimos_fechamentos(fundo: models.Fundo, n: int = 7) -> list[LinhaCota]:
    """Os n últimos fechamentos do fundo, do mais antigo para o mais novo."""
    recentes = list(fundo.fechamentos.order_by("-data")[:n])[::-1]
    linhas = []
    anterior: Decimal | None = None
    for f in recentes:
        variacao = None if anterior in (None, 0) else (f.cota / anterior - 1) * 100
        linhas.append(LinhaCota(data=f.data, cota=f.cota, variacao=variacao))
        anterior = f.cota
    return linhas


def _rebasar(valores: dict[date, Decimal], datas: list[date]) -> list[float | None]:
    """Série em base 100 na primeira data com dado. Dia sem dado vira None."""
    base = next((valores[d] for d in datas if d in valores), None)
    if base is None or base == 0:
        return [None] * len(datas)
    return [float(valores[d] / base * 100) if d in valores else None for d in datas]


def _serie_cdi(datas: list[date]) -> list[float]:
    """CDI acumulado, capitalizado em dia útil, base 100 na primeira data."""
    inicio, fim = datas[0], datas[-1]
    taxas = dict(
        models.TaxaCDI.objects.filter(data__gte=inicio, data__lte=fim).values_list(
            "data", "taxa_diaria"
        )
    )
    corrente = (
        models.TaxaCDI.objects.filter(data__lte=inicio)
        .order_by("-data")
        .values_list("taxa_diaria", flat=True)
        .first()
    ) or Decimal("0")

    alvo, valores, acumulado = set(datas), [], Decimal("100")
    dia = inicio
    while dia <= fim:
        corrente = taxas.get(dia, corrente)
        if dia > inicio and eh_dia_util(dia):
            acumulado *= 1 + corrente
        if dia in alvo:
            valores.append(float(acumulado))
        dia += timedelta(days=1)
    return valores


def serie_comparada(fundo: models.Fundo) -> dict[str, list]:
    """Cota do fundo contra CDI, IBOV e S&P — todos em base 100 no mesmo dia.

    Sem normalizar não há gráfico: a cota vale ~100 e o IBOV, ~186.000.
    """
    fechamentos = list(fundo.fechamentos.order_by("data"))
    if not fechamentos:
        return {"datas": [], "series": []}

    datas = [f.data for f in fechamentos]
    cotas = {f.data: f.cota for f in fechamentos}
    indices = {
        codigo: dict(
            models.Benchmark.objects.filter(codigo=codigo, data__in=datas).values_list(
                "data", "valor"
            )
        )
        for codigo in (models.Benchmark.Codigo.IBOV, models.Benchmark.Codigo.SP500)
    }

    return {
        "datas": [d.strftime("%d/%m") for d in datas],
        "series": [
            {"nome": "Meu fundo", "chave": "fundo", "valores": _rebasar(cotas, datas)},
            {"nome": "CDI", "chave": "cdi", "valores": _serie_cdi(datas)},
            {
                "nome": "Ibovespa",
                "chave": "ibov",
                "valores": _rebasar(indices[models.Benchmark.Codigo.IBOV], datas),
            },
            {
                "nome": "S&P 500",
                "chave": "sp",
                "valores": _rebasar(indices[models.Benchmark.Codigo.SP500], datas),
            },
        ],
    }
