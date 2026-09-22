"""Motor do Desafio Fenrir.

Funções puras: sem rede, sem banco, sem framework. Recebem o ledger e devolvem
o estado. É o que torna o motor testável — e o que faltava na versão anterior,
onde a economia toda morava dentro do handler de um botão do Streamlit.

Convenções (regulamento §3.2 e §4):
  - Todo fundo começa com R$ 100.000.000,00 e cota base 100,00.
  - Caixa livre rende CDI em dias úteis, capitalizado.
  - Não há alavancagem: |comprado| + |vendido| <= patrimônio.
  - Ativo estrangeiro é convertido para BRL pelo câmbio do momento da execução.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from .calendario import dias_uteis
from .custos import lancamento_aluguel
from .models import (
    Ativo,
    Direcao,
    EventoCaixa,
    Fechamento,
    Fundo,
    Lancamento,
    Ordem,
    Rejeicao,
    ResultadoValidacao,
    Trade,
)

CENTAVO = Decimal("0.01")


# --------------------------------------------------------------------------
# Estado derivado
# --------------------------------------------------------------------------
def posicoes(eventos: Iterable[EventoCaixa], ate: date | None = None) -> dict[str, int]:
    """Posição por ticker: soma das quantidades assinadas do ledger.

    Aceita o ledger misto (trades + lançamentos) e ignora o que não é trade.
    Posições zeradas são omitidas. Valores negativos são posições vendidas.
    """
    acumulado: dict[str, int] = defaultdict(int)
    for evento in eventos:
        if not isinstance(evento, Trade):
            continue
        if ate is not None and evento.executado_em > ate:
            continue
        acumulado[evento.ticker] += evento.quantidade
    return {ticker: qtd for ticker, qtd in acumulado.items() if qtd != 0}


def caixa(
    fundo: Fundo,
    eventos: Iterable[EventoCaixa],
    taxa_cdi_diaria: Decimal,
    ate: date,
) -> Decimal:
    """Saldo de caixa em `ate`, com CDI capitalizado entre os eventos.

    O rendimento é aplicado sobre o saldo vigente em cada intervalo e incorporado
    ao próprio saldo — operar não zera os juros acumulados, que era o defeito da
    versão anterior.

    Num mesmo dia os trades liquidam antes dos lançamentos (o aluguel do short
    incide sobre a posição que ficou de pé no fechamento).
    """
    relevantes = sorted(
        (e for e in eventos if e.executado_em <= ate),
        key=_ordem_no_dia,
    )

    saldo = fundo.caixa_inicial
    cursor = fundo.inicio
    for evento in relevantes:
        saldo = _render(saldo, cursor, evento.executado_em, taxa_cdi_diaria)
        saldo += evento.fluxo_caixa
        cursor = evento.executado_em
    return _render(saldo, cursor, ate, taxa_cdi_diaria)


def _ordem_no_dia(evento: EventoCaixa) -> tuple[date, int, str]:
    if isinstance(evento, Trade):
        return (evento.executado_em, 0, evento.ticker)
    return (evento.executado_em, 1, evento.tipo.value)


def _render(saldo: Decimal, de: date, ate: date, taxa_diaria: Decimal) -> Decimal:
    dias = dias_uteis(de, ate)
    if dias == 0:
        return saldo
    return saldo * (Decimal(1) + taxa_diaria) ** dias


def valor_posicoes(
    posicoes_atuais: Mapping[str, int],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
) -> Decimal:
    """Marcação a mercado em BRL. Posição vendida entra com valor negativo."""
    total = Decimal(0)
    for ticker, quantidade in posicoes_atuais.items():
        if ticker not in precos:
            raise KeyError(f"Sem preço para marcar {ticker}.")
        total += Decimal(quantidade) * precos[ticker] * cambios.get(ticker, Decimal(1))
    return total


def exposicao_bruta(
    posicoes_atuais: Mapping[str, int],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
) -> Decimal:
    """Soma dos módulos das posições — a métrica que o limite de alavancagem usa."""
    total = Decimal(0)
    for ticker, quantidade in posicoes_atuais.items():
        total += abs(Decimal(quantidade)) * precos[ticker] * cambios.get(ticker, Decimal(1))
    return total


def patrimonio(saldo_caixa: Decimal, valor_mtm: Decimal) -> Decimal:
    return saldo_caixa + valor_mtm


def cota(fundo: Fundo, patrimonio_atual: Decimal) -> Decimal:
    return patrimonio_atual / fundo.cotas_emitidas


# --------------------------------------------------------------------------
# Execução de ordens
# --------------------------------------------------------------------------
def executar(
    ordem: Ordem,
    fundo: Fundo,
    ledger_do_fundo: list[EventoCaixa],
    universo: Mapping[str, Ativo],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
    taxa_cdi_diaria: Decimal,
    data_execucao: date,
) -> ResultadoValidacao:
    """Valida a boleta contra o estado atual e devolve o Trade ou a Rejeição.

    `ledger_do_fundo` contém apenas os trades do fundo da boleta — os limites de
    risco são por fundo.

    Não altera nada: quem persiste o resultado é a camada de cima. Assim a mesma
    ordem não pode ser aplicada duas vezes por acidente.
    """
    if ordem.ticker not in universo:
        return Rejeicao(f"{ordem.ticker} não está na whitelist do desafio.")
    if ordem.ticker not in precos:
        return Rejeicao(f"Sem preço de execução disponível para {ordem.ticker}.")

    quantidade = ordem.quantidade * ordem.direcao.sinal
    candidato = Trade(
        fundo=fundo.nome,
        ticker=ordem.ticker,
        quantidade=quantidade,
        preco_nativo=precos[ordem.ticker],
        cambio=cambios.get(ordem.ticker, Decimal(1)),
        executado_em=data_execucao,
    )

    saldo = caixa(fundo, ledger_do_fundo, taxa_cdi_diaria, data_execucao)
    posicoes_depois = posicoes([*ledger_do_fundo, candidato], ate=data_execucao)
    patrimonio_depois = patrimonio(
        saldo + candidato.fluxo_caixa,
        valor_posicoes(posicoes_depois, precos, cambios),
    )
    exposicao_depois = exposicao_bruta(posicoes_depois, precos, cambios)

    # Regulamento §3.2: comprado e vendido somados em módulo não podem passar do
    # patrimônio. É a mesma regra do Desafio JGP, que o Fenrir espelha.
    if exposicao_depois > patrimonio_depois:
        return Rejeicao(
            "Alavancagem: exposição bruta de "
            f"R$ {exposicao_depois:,.2f} excede o patrimônio de "
            f"R$ {patrimonio_depois:,.2f}."
        )

    return candidato


def executar_lote(
    ordens: Iterable[Ordem],
    fundos: Mapping[str, Fundo],
    ledger: list[EventoCaixa],
    universo: Mapping[str, Ativo],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
    taxa_cdi_diaria: Decimal,
    data_execucao: date,
) -> list[tuple[Ordem, ResultadoValidacao]]:
    """Liquida a fila da semana na ordem de chegada.

    Cada ordem é validada contra o ledger já acrescido das ordens anteriores do
    mesmo lote — senão dois pedidos sozinhos válidos estourariam o limite juntos.

    Devolve cada boleta junto do seu resultado (Trade ou Rejeicao). O par evita
    que a camada de cima precise adivinhar qual resultado pertence a qual ordem.
    """
    resultados: list[tuple[Ordem, ResultadoValidacao]] = []
    novos: list[Trade] = []

    for ordem in sorted(ordens, key=lambda o: o.enviada_em):
        fundo = fundos[ordem.fundo]
        ledger_do_fundo = [t for t in [*ledger, *novos] if t.fundo == fundo.nome]
        resultado = executar(
            ordem,
            fundo,
            ledger_do_fundo,
            universo,
            precos,
            cambios,
            taxa_cdi_diaria,
            data_execucao,
        )
        if isinstance(resultado, Trade):
            novos.append(resultado)
        resultados.append((ordem, resultado))

    return resultados


# --------------------------------------------------------------------------
# Fechamento
# --------------------------------------------------------------------------
def fechar(
    fundo: Fundo,
    eventos: Iterable[EventoCaixa],
    precos: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
    taxa_cdi_diaria: Decimal,
    data: date,
) -> Fechamento:
    """Foto do fundo na data, a partir do ledger como ele está.

    Não gera custo de carrego — quem faz isso é `apurar_dia`, que é a rotina
    oficial do fechamento diário.
    """
    do_fundo = [e for e in eventos if e.fundo == fundo.nome]
    saldo = caixa(fundo, do_fundo, taxa_cdi_diaria, data)
    posicoes_atuais = posicoes(do_fundo, ate=data)
    mtm = valor_posicoes(posicoes_atuais, precos, cambios)
    total = patrimonio(saldo, mtm)

    return Fechamento(
        fundo=fundo.nome,
        data=data,
        caixa=saldo.quantize(CENTAVO),
        valor_posicoes=mtm.quantize(CENTAVO),
        patrimonio=total.quantize(CENTAVO),
        cota=cota(fundo, total).quantize(CENTAVO),
    )


def apurar_dia(
    fundo: Fundo,
    eventos: Iterable[EventoCaixa],
    precos_fechamento: Mapping[str, Decimal],
    cambios: Mapping[str, Decimal],
    taxa_cdi_diaria: Decimal,
    dia: date,
) -> tuple[Fechamento, Lancamento | None]:
    """Rotina oficial de fechamento do dia, rodada após o mercado fechar.

    Devolve a foto do fundo e o lançamento de aluguel do dia (None se o fundo
    não estiver vendido). O lançamento precisa ser persistido no ledger pela
    camada de cima **antes** do próximo fechamento — senão o custo some.

    Só usa preço de fechamento: a cota do Fenrir muda uma vez por dia, depois do
    mercado fechar, e não durante o pregão.
    """
    do_fundo = [e for e in eventos if e.fundo == fundo.nome]
    posicoes_no_fechamento = posicoes(do_fundo, ate=dia)

    aluguel = lancamento_aluguel(
        fundo.nome, posicoes_no_fechamento, precos_fechamento, cambios, dia
    )
    ledger_do_dia = [*do_fundo, aluguel] if aluguel else do_fundo

    fechamento = fechar(
        fundo, ledger_do_dia, precos_fechamento, cambios, taxa_cdi_diaria, dia
    )
    return fechamento, aluguel
