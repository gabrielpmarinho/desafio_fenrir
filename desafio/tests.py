"""Testes de integração da Mesa.

Os testes do motor vivem em `tests/` e rodam com pytest, sem Django. Estes aqui
exercitam a corrente completa — banco, adapters, comandos — e rodam com
`python manage.py test desafio`.

Nada aqui toca a internet: preços, câmbio e CDI são gravados na mão.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from . import models

SEGUNDA = date(2026, 10, 5)
TERCA = date(2026, 10, 6)


class MesaTestCase(TestCase):
    def setUp(self):
        self.fundo = models.Fundo.objects.create(
            nome="Astra Capital",
            slug="astra-capital",
            caixa_inicial=Decimal("100000000.00"),
            inicio=SEGUNDA,
        )
        for dia in (SEGUNDA, TERCA):
            models.PrecoFechamento.objects.create(
                ticker="PETR4.SA", data=dia, preco=Decimal("40.00")
            )
            models.PrecoFechamento.objects.create(
                ticker="VALE3.SA", data=dia, preco=Decimal("60.00")
            )
            models.PrecoFechamento.objects.create(
                ticker="SPY", data=dia, preco=Decimal("500.00")
            )
            models.Cotacao.objects.create(data=dia, usd_brl=Decimal("5.40"))
            models.TaxaCDI.objects.create(data=dia, taxa_diaria=Decimal("0.0005"))

    def _boleta(self, ticker, quantidade, direcao):
        return models.Ordem.objects.create(
            fundo=self.fundo, ticker=ticker, quantidade=quantidade, direcao=direcao
        )

    def _rodar(self, comando, **kwargs):
        saida = StringIO()
        call_command(comando, stdout=saida, stderr=saida, **kwargs)
        return saida.getvalue()


class TestLiquidacao(MesaTestCase):
    def test_ordem_vira_trade_ao_preco_de_fechamento(self):
        boleta = self._boleta("PETR4.SA", 1000, models.Ordem.Direcao.COMPRA)

        self._rodar("liquidar_semana", data="2026-10-05")

        boleta.refresh_from_db()
        self.assertEqual(boleta.status, models.Ordem.Status.EXECUTADA)
        trade = models.Trade.objects.get()
        self.assertEqual(trade.quantidade, 1000)
        self.assertEqual(trade.preco_nativo, Decimal("40.00000000"))
        self.assertEqual(trade.executado_em, SEGUNDA)

    def test_venda_grava_quantidade_negativa(self):
        self._boleta("VALE3.SA", 500, models.Ordem.Direcao.VENDA)

        self._rodar("liquidar_semana", data="2026-10-05")

        self.assertEqual(models.Trade.objects.get().quantidade, -500)

    def test_ativo_estrangeiro_guarda_o_cambio_do_dia(self):
        self._boleta("SPY", 10, models.Ordem.Direcao.COMPRA)

        self._rodar("liquidar_semana", data="2026-10-05")

        self.assertEqual(models.Trade.objects.get().cambio, Decimal("5.40000000"))

    def test_ordem_alavancada_e_rejeitada_sem_virar_trade(self):
        boleta = self._boleta("PETR4.SA", 3_000_000, models.Ordem.Direcao.COMPRA)

        self._rodar("liquidar_semana", data="2026-10-05")

        boleta.refresh_from_db()
        self.assertEqual(boleta.status, models.Ordem.Status.REJEITADA)
        self.assertIn("Alavancagem", boleta.motivo_rejeicao)
        self.assertFalse(models.Trade.objects.exists())

    def test_simular_nao_grava_nada(self):
        boleta = self._boleta("PETR4.SA", 1000, models.Ordem.Direcao.COMPRA)

        saida = self._rodar("liquidar_semana", data="2026-10-05", simular=True)

        boleta.refresh_from_db()
        self.assertIn("[simulação]", saida)
        self.assertEqual(boleta.status, models.Ordem.Status.PENDENTE)
        self.assertFalse(models.Trade.objects.exists())

    def test_cada_boleta_recebe_o_proprio_resultado(self):
        """A primeira passa, a segunda estoura o limite — e cada uma tem que
        terminar com o status certo, não trocado."""
        primeira = self._boleta("PETR4.SA", 2_000_000, models.Ordem.Direcao.COMPRA)
        segunda = self._boleta("PETR4.SA", 2_000_000, models.Ordem.Direcao.COMPRA)

        self._rodar("liquidar_semana", data="2026-10-05")

        primeira.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(primeira.status, models.Ordem.Status.EXECUTADA)
        self.assertEqual(segunda.status, models.Ordem.Status.REJEITADA)


class TestFechamento(MesaTestCase):
    def test_cota_inicial_vale_100(self):
        self._rodar("fechar_dia", data="2026-10-05")

        fechamento = models.Fechamento.objects.get()
        self.assertEqual(fechamento.cota, Decimal("100.00"))
        self.assertEqual(fechamento.patrimonio, Decimal("100000000.00"))

    def test_short_gera_lancamento_de_aluguel(self):
        self._boleta("VALE3.SA", 1000, models.Ordem.Direcao.VENDA)
        self._rodar("liquidar_semana", data="2026-10-05")

        self._rodar("fechar_dia", data="2026-10-05")

        aluguel = models.Lancamento.objects.get()
        self.assertEqual(aluguel.tipo, models.Lancamento.Tipo.ALUGUEL_SHORT)
        self.assertEqual(aluguel.valor, Decimal("-12.00"))  # 60.000 x 0,02%
        self.assertIn("VALE3.SA", aluguel.descricao)

    def test_carteira_comprada_nao_paga_aluguel(self):
        self._boleta("PETR4.SA", 1000, models.Ordem.Direcao.COMPRA)
        self._rodar("liquidar_semana", data="2026-10-05")

        self._rodar("fechar_dia", data="2026-10-05")

        self.assertFalse(models.Lancamento.objects.exists())

    def test_rodar_duas_vezes_no_mesmo_dia_nao_cobra_em_dobro(self):
        """O erro operacional mais fácil de cometer: rodar o fechamento de novo."""
        self._boleta("VALE3.SA", 1000, models.Ordem.Direcao.VENDA)
        self._rodar("liquidar_semana", data="2026-10-05")

        self._rodar("fechar_dia", data="2026-10-05")
        saida = self._rodar("fechar_dia", data="2026-10-05")

        self.assertIn("já apurado", saida)
        self.assertEqual(models.Fechamento.objects.count(), 1)
        self.assertEqual(models.Lancamento.objects.count(), 1)

    def test_refazer_substitui_sem_duplicar(self):
        self._boleta("VALE3.SA", 1000, models.Ordem.Direcao.VENDA)
        self._rodar("liquidar_semana", data="2026-10-05")
        self._rodar("fechar_dia", data="2026-10-05")

        self._rodar("fechar_dia", data="2026-10-05", refazer=True)

        self.assertEqual(models.Fechamento.objects.count(), 1)
        self.assertEqual(models.Lancamento.objects.count(), 1)

    def test_aluguel_acumula_dia_a_dia(self):
        self._boleta("VALE3.SA", 1000, models.Ordem.Direcao.VENDA)
        self._rodar("liquidar_semana", data="2026-10-05")

        self._rodar("fechar_dia", data="2026-10-05")
        self._rodar("fechar_dia", data="2026-10-06")

        self.assertEqual(models.Lancamento.objects.count(), 2)
        total = sum(l.valor for l in models.Lancamento.objects.all())
        self.assertEqual(total, Decimal("-24.00"))

    def test_fundo_que_ainda_nao_comecou_nao_e_apurado(self):
        models.Fundo.objects.create(
            nome="Citadel Capital",
            slug="citadel-capital",
            inicio=date(2026, 11, 3),
        )

        self._rodar("fechar_dia", data="2026-10-05")

        self.assertEqual(models.Fechamento.objects.count(), 1)
        self.assertEqual(models.Fechamento.objects.get().fundo, self.fundo)

    def test_dia_nao_util_nao_apura(self):
        saida = self._rodar("fechar_dia", data="2026-10-11")  # domingo

        self.assertIn("não é dia útil", saida)
        self.assertFalse(models.Fechamento.objects.exists())

    def test_cdi_rende_no_caixa_entre_os_dias(self):
        self._rodar("fechar_dia", data="2026-10-05")
        self._rodar("fechar_dia", data="2026-10-06")

        primeiro, segundo = models.Fechamento.objects.order_by("data")
        self.assertGreater(segundo.cota, primeiro.cota)


class TelaTestCase(MesaTestCase):
    """Base das telas: usuário logado, fundo próprio e um fundo rival.

    Sem testes aqui de propósito — classe de teste que herda outra classe de
    teste re-executa os testes dela.
    """

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        self.rival = models.Fundo.objects.create(
            nome="Citadel Capital", slug="citadel-capital", inicio=SEGUNDA
        )
        self.usuario = User.objects.create_user("gabriel", password="senha-de-teste")
        models.Participante.objects.create(
            usuario=self.usuario, fundo=self.fundo, nucleo="MACRO"
        )

    def _logar(self):
        self.client.force_login(self.usuario)


class TestTelas(TelaTestCase):
    """Telas do participante. O foco é isolamento entre fundos e a janela."""

    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/entrar/", resposta["Location"])

    def test_usuario_sem_fundo_nao_entra(self):
        from django.contrib.auth.models import User

        orfao = User.objects.create_user("orfao", password="x")
        self.client.force_login(orfao)

        self.assertEqual(self.client.get("/").status_code, 404)

    def test_dashboard_mostra_o_proprio_fundo(self):
        self._logar()

        resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Astra Capital")
        self.assertEqual(resposta.context["fundo"], self.fundo)

    def test_boleta_nasce_no_fundo_do_usuario_logado(self):
        """Mesmo que o POST tente indicar outro fundo."""
        self._logar()
        with mock.patch("desafio.forms.janela_aberta", return_value=True):
            self.client.post(
                "/ordens/",
                {
                    "ticker": "PETR4.SA",
                    "direcao": "COMPRA",
                    "quantidade": 100,
                    "fundo": self.rival.id,
                },
            )

        ordem = models.Ordem.objects.get()
        self.assertEqual(ordem.fundo, self.fundo)
        self.assertEqual(ordem.enviada_por, self.usuario)

    def test_fora_da_janela_o_post_e_recusado(self):
        """A trava é no servidor, não só no esconde-formulário da tela."""
        self._logar()
        with mock.patch("desafio.forms.janela_aberta", return_value=False):
            resposta = self.client.post(
                "/ordens/",
                {"ticker": "PETR4.SA", "direcao": "COMPRA", "quantidade": 100},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(models.Ordem.objects.exists())

    def test_quantidade_zero_nao_vira_boleta(self):
        self._logar()
        with mock.patch("desafio.forms.janela_aberta", return_value=True):
            self.client.post(
                "/ordens/",
                {"ticker": "PETR4.SA", "direcao": "COMPRA", "quantidade": 0},
            )

        self.assertFalse(models.Ordem.objects.exists())

    def test_ticker_fora_da_whitelist_nao_vira_boleta(self):
        self._logar()
        with mock.patch("desafio.forms.janela_aberta", return_value=True):
            self.client.post(
                "/ordens/",
                {"ticker": "TSLA", "direcao": "COMPRA", "quantidade": 10},
            )

        self.assertFalse(models.Ordem.objects.exists())

    def test_participante_nao_ve_boleta_de_outro_fundo(self):
        models.Ordem.objects.create(
            fundo=self.rival, ticker="VALE3.SA", quantidade=99, direcao="COMPRA"
        )
        self._logar()

        resposta = self.client.get("/ordens/")

        self.assertNotIn(99, [o.quantidade for o in resposta.context["ordens"]])

    def test_extrato_traz_o_aluguel_do_proprio_fundo(self):
        self._boleta("VALE3.SA", 1000, models.Ordem.Direcao.VENDA)
        self._rodar("liquidar_semana", data="2026-10-05")
        self._rodar("fechar_dia", data="2026-10-05")
        self._logar()

        resposta = self.client.get("/extrato/")

        self.assertContains(resposta, "Aluguel de short")
        self.assertContains(resposta, "-12,00")

    def test_ranking_lista_todos_os_fundos_apurados(self):
        self._rodar("fechar_dia", data="2026-10-05")
        self._logar()

        resposta = self.client.get("/ranking/")

        self.assertEqual(len(resposta.context["linhas"]), 2)
        self.assertContains(resposta, "seu fundo")


class TestCancelamento(TelaTestCase):
    """Cancelar boleta pendente — some da fila, fica no histórico."""

    def test_cancelar_muda_o_status_e_tira_da_liquidacao(self):
        ordem = self._boleta("PETR4.SA", 100, models.Ordem.Direcao.COMPRA)
        self._logar()

        resposta = self.client.post(f"/ordens/{ordem.id}/cancelar/")

        self.assertEqual(resposta.status_code, 302)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, models.Ordem.Status.CANCELADA)

        self._rodar("liquidar_semana", data="2026-10-05")
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, models.Ordem.Status.CANCELADA)
        self.assertEqual(models.Trade.objects.count(), 0)

    def test_get_nao_cancela(self):
        ordem = self._boleta("PETR4.SA", 100, models.Ordem.Direcao.COMPRA)
        self._logar()

        resposta = self.client.get(f"/ordens/{ordem.id}/cancelar/")

        self.assertEqual(resposta.status_code, 404)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, models.Ordem.Status.PENDENTE)

    def test_nao_cancela_boleta_de_outro_fundo(self):
        alheia = models.Ordem.objects.create(
            fundo=self.rival,
            ticker="PETR4.SA",
            quantidade=100,
            direcao=models.Ordem.Direcao.COMPRA,
        )
        self._logar()

        resposta = self.client.post(f"/ordens/{alheia.id}/cancelar/")

        self.assertEqual(resposta.status_code, 404)
        alheia.refresh_from_db()
        self.assertEqual(alheia.status, models.Ordem.Status.PENDENTE)

    def test_nao_cancela_boleta_ja_executada(self):
        ordem = self._boleta("PETR4.SA", 100, models.Ordem.Direcao.COMPRA)
        self._rodar("liquidar_semana", data="2026-10-05")
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, models.Ordem.Status.EXECUTADA)
        self._logar()

        resposta = self.client.post(f"/ordens/{ordem.id}/cancelar/")

        self.assertEqual(resposta.status_code, 404)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, models.Ordem.Status.EXECUTADA)


class TestMuralEComparacao(TelaTestCase):
    """Avisos da Diretoria e o gráfico da carteira contra o mercado."""

    def test_aviso_ativo_aparece_na_carteira(self):
        models.Aviso.objects.create(
            titulo="Feriado na B3", mensagem="Dia 12/10 não há pregão."
        )
        self._logar()

        resposta = self.client.get("/")

        self.assertContains(resposta, "Feriado na B3")
        self.assertContains(resposta, "Avisos do Diretor de Competições")

    def test_aviso_inativo_ou_vencido_nao_aparece(self):
        models.Aviso.objects.create(titulo="Desligado", mensagem="x", ativo=False)
        models.Aviso.objects.create(
            titulo="Vencido", mensagem="x", vigente_ate=date(2020, 1, 1)
        )
        self._logar()

        resposta = self.client.get("/")

        self.assertNotContains(resposta, "Desligado")
        self.assertNotContains(resposta, "Vencido")

    def test_serie_comparada_rebasa_tudo_em_100(self):
        from desafio.servicos import carteira

        models.Benchmark.objects.create(
            codigo="IBOV", data=SEGUNDA, valor=Decimal("180000")
        )
        models.Benchmark.objects.create(
            codigo="IBOV", data=TERCA, valor=Decimal("181800")
        )
        self._rodar("fechar_dia", data="2026-10-05")
        self._rodar("fechar_dia", data="2026-10-06")

        serie = carteira.serie_comparada(self.fundo)

        chaves = [s["chave"] for s in serie["series"]]
        self.assertEqual(chaves, ["fundo", "cdi", "ibov", "sp"])
        for s in serie["series"]:
            if s["chave"] != "sp":  # sem S&P gravado, a série vem vazia
                self.assertEqual(s["valores"][0], 100.0)
        ibov = next(s for s in serie["series"] if s["chave"] == "ibov")
        self.assertAlmostEqual(ibov["valores"][1], 101.0, places=6)
        sp = next(s for s in serie["series"] if s["chave"] == "sp")
        self.assertIsNone(sp["valores"][0])

    def test_ranking_congela_na_semana_fechada(self):
        from desafio.servicos import carteira

        # Sexta 02/10 apurada e segunda 05/10 também: na semana de 05/10 a foto
        # tem que continuar sendo a de sexta.
        models.Fechamento.objects.create(
            fundo=self.fundo,
            data=date(2026, 10, 2),
            caixa=Decimal("100000000"),
            valor_posicoes=Decimal("0"),
            patrimonio=Decimal("100000000"),
            cota=Decimal("100.00"),
        )
        models.Fechamento.objects.create(
            fundo=self.fundo,
            data=SEGUNDA,
            caixa=Decimal("100000000"),
            valor_posicoes=Decimal("0"),
            patrimonio=Decimal("100000000"),
            cota=Decimal("105.00"),
        )

        self.assertEqual(carteira.data_do_ranking(hoje=date(2026, 10, 7)), date(2026, 10, 2))
        linhas = carteira.ranking(hoje=date(2026, 10, 7))
        self.assertEqual(linhas[0].cota, Decimal("100.00"))
