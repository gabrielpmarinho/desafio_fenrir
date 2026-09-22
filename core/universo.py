"""Whitelist do desafio (regulamento §3.3).

Mantida aqui como fonte única. Quando o Django entrar, vira seed de migration —
não duplicar a lista em template nem em formulário.
"""

from __future__ import annotations

from .models import Ativo, Moeda


def _br(ticker: str, nome: str) -> Ativo:
    return Ativo(ticker=ticker, nome=nome, moeda=Moeda.BRL)


def _us(ticker: str, nome: str) -> Ativo:
    return Ativo(ticker=ticker, nome=nome, moeda=Moeda.USD)


ETFS = [
    _us("SPY", "S&P 500"),
    _us("QQQ", "Nasdaq 100"),
    _br("BOVA11.SA", "Ibovespa"),
    _us("MCHI", "Bolsa da China"),
    _us("TLT", "Títulos EUA 20+ anos"),
    _us("USO", "Petróleo"),
    _us("GLD", "Ouro"),
    _br("IMAB11.SA", "Renda Fixa/Inflação BR"),
    _br("XFIX11.SA", "Fundos Imobiliários BR"),
    _us("VNQ", "Imóveis EUA"),
    _us("XLV", "Saúde EUA"),
    _us("IBIT", "Bitcoin"),
    _us("NLR", "Energia Nuclear"),
    _us("BOTZ", "IA e Robótica"),
    _us("PAVE", "Infraestrutura EUA"),
    _us("XLK", "Tecnologia EUA"),
    _us("XLF", "Financeiro EUA"),
]

ACOES_B3 = [
    _br("PETR4.SA", "Petrobras"),
    _br("VALE3.SA", "Vale"),
    _br("ITUB4.SA", "Itaú"),
    _br("BBAS3.SA", "Banco do Brasil"),
    _br("WEGE3.SA", "WEG"),
    _br("ELET3.SA", "Eletrobras"),
    _br("RENT3.SA", "Localiza"),
    _br("RADL3.SA", "Raia Drogasil"),
    _br("SUZB3.SA", "Suzano"),
    _br("JBSS3.SA", "JBS"),
    _br("B3SA3.SA", "B3"),
    _br("ABEV3.SA", "Ambev"),
    _br("MGLU3.SA", "Magazine Luiza"),
]

UNIVERSO: dict[str, Ativo] = {ativo.ticker: ativo for ativo in [*ETFS, *ACOES_B3]}
