from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Usuario
from apps.reservas.models import Reserva
from apps.reservas.services import cancelar_reserva
from apps.veiculos.models import Veiculo

from .models import Pagamento
from .services import PagamentoInvalido, simular_pagamento


class PagamentoBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.proprietario = Usuario.objects.create_user(
            username="proprietario",
            email="proprietario@example.com",
            password="senha-de-teste",
        )
        cls.locatario = Usuario.objects.create_user(
            username="locatario",
            email="locatario@example.com",
            password="senha-de-teste",
        )
        cls.outro = Usuario.objects.create_user(
            username="outro",
            email="outro@example.com",
            password="senha-de-teste",
        )
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.proprietario,
            caracteristicas="Veículo de teste",
            cidade="São Paulo",
            categoria="Hatch",
            cambio="Manual",
            combustivel="Flex",
            passageiros=5,
            preco_diaria=Decimal("150.00"),
            ativo=True,
            bloqueado=False,
            aprovacao=Veiculo.Aprovacao.APROVADO,
        )

    def criar_reserva(
        self, *, status=Reserva.Status.ACEITA, inicio_dias=5,
        percentual_comissao=Decimal("15.00"),
    ):
        inicio = timezone.localdate() + timedelta(days=inicio_dias)
        return Reserva.objects.create(
            veiculo=self.veiculo,
            locatario=self.locatario,
            inicio=inicio,
            fim=inicio + timedelta(days=3),
            status=status,
            preco_diaria=Decimal("150.00"),
            valor_diarias=Decimal("450.00"),
            taxas=Decimal("0.00"),
            total=Decimal("450.00"),
            percentual_comissao=percentual_comissao,
        )


class SimulacaoPagamentoTests(PagamentoBaseTests):
    def test_servico_rejeita_meio_e_resultado_invalidos(self):
        reserva = self.criar_reserva()
        for meio, resultado in (
            ("boleto", "aprovado"), ("", "aprovado"),
            ("pix", "desconhecido"), ("cartao", ""),
        ):
            with self.subTest(meio=meio, resultado=resultado):
                with self.assertRaises(PagamentoInvalido):
                    simular_pagamento(
                        reserva=reserva, meio=meio, resultado=resultado,
                    )
                self.assertFalse(Pagamento.objects.exists())

    def test_pagamento_respeita_percentual_contratado(self):
        from apps.administracao.models import ConfiguracaoComissao

        reserva = self.criar_reserva(percentual_comissao=Decimal("10.00"))
        ConfiguracaoComissao.objects.update_or_create(
            pk=1, defaults={"percentual": "25.00"},
        )
        Veiculo.objects.filter(pk=self.veiculo.pk).update(
            preco_diaria="999.00",
        )
        # Alterar a instância recebida não muda o snapshot persistido.
        reserva.total = Decimal("1.00")
        reserva.percentual_comissao = Decimal("0.00")
        pagamento = simular_pagamento(
            reserva=reserva, meio=Pagamento.Meio.PIX, resultado="aprovado",
        )

        self.assertEqual(pagamento.valor_bruto, Decimal("450.00"))
        self.assertEqual(pagamento.comissao, Decimal("45.00"))
        self.assertEqual(pagamento.repasse_proprietario, Decimal("405.00"))
        self.assertEqual(
            pagamento.comissao + pagamento.repasse_proprietario,
            pagamento.valor_bruto,
        )

    def test_servico_revalida_status_apos_carregar_reserva(self):
        reserva = self.criar_reserva()
        cancelar_reserva(reserva)

        with self.assertRaises(PagamentoInvalido):
            simular_pagamento(
                reserva=reserva, meio=Pagamento.Meio.PIX, resultado="aprovado",
            )
        self.assertFalse(Pagamento.objects.exists())

    def test_cancelamento_nao_transforma_recusa_em_estorno(self):
        reserva = self.criar_reserva()
        pagamento = simular_pagamento(
            reserva=reserva, meio=Pagamento.Meio.CARTAO, resultado="recusado",
        )
        cancelar_reserva(reserva)
        pagamento.refresh_from_db()

        self.assertEqual(pagamento.status, Pagamento.Status.RECUSADO)
        with self.assertRaises(PagamentoInvalido):
            simular_pagamento(
                reserva=reserva, meio=Pagamento.Meio.PIX, resultado="aprovado",
            )

    def test_pagamento_aprovado_grava_valores_da_reserva(self):
        reserva = self.criar_reserva()

        pagamento = simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )

        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        self.assertEqual(pagamento.meio, Pagamento.Meio.PIX)
        self.assertEqual(pagamento.valor_bruto, reserva.total)
        self.assertEqual(pagamento.comissao, Decimal("67.50"))
        self.assertEqual(pagamento.repasse_proprietario, Decimal("382.50"))

    def test_pagamento_recusado_pode_ser_repetido(self):
        reserva = self.criar_reserva()
        simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.CARTAO,
            resultado="recusado",
        )

        pagamento = simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )

        self.assertEqual(Pagamento.objects.count(), 1)
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)

    def test_reserva_solicitada_nao_aceita_pagamento(self):
        reserva = self.criar_reserva(status=Reserva.Status.SOLICITADA)

        with self.assertRaises(PagamentoInvalido):
            simular_pagamento(
                reserva=reserva,
                meio=Pagamento.Meio.PIX,
                resultado="aprovado",
            )

    def test_pagamento_aprovado_nao_pode_ser_repetido(self):
        reserva = self.criar_reserva()
        simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )

        with self.assertRaises(PagamentoInvalido):
            simular_pagamento(
                reserva=reserva,
                meio=Pagamento.Meio.CARTAO,
                resultado="aprovado",
            )

    def test_cancelamento_estorna_pagamento_aprovado(self):
        reserva = self.criar_reserva()
        pagamento = simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )

        cancelar_reserva(reserva)

        reserva.refresh_from_db()
        pagamento.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)
        self.assertEqual(pagamento.status, Pagamento.Status.ESTORNADO)


class PagarReservaViewTests(PagamentoBaseTests):
    def test_formulario_explica_simulacao_e_nao_coleta_dados_bancarios(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)
        response = self.client.get(reverse("pagamentos:pagar", args=[reserva.pk]))

        self.assertContains(response, "Nenhum valor real será cobrado")
        self.assertContains(response, "Não informe dados de cartão")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            set(response.context["form"].fields), {"meio", "resultado"},
        )

    def test_visitante_precisa_entrar_para_get_e_post(self):
        reserva = self.criar_reserva()
        url = reverse("pagamentos:pagar", args=[reserva.pk])
        for metodo in (self.client.get, self.client.post):
            response = metodo(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("core:entrar"), response.url)
        self.assertFalse(Pagamento.objects.exists())

    def test_post_exige_csrf(self):
        reserva = self.criar_reserva()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.locatario)
        url = reverse("pagamentos:pagar", args=[reserva.pk])
        dados = {"meio": "pix", "resultado": "aprovado"}

        self.assertEqual(client.post(url, dados).status_code, 403)
        self.assertFalse(Pagamento.objects.exists())
        client.get(url)
        dados["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, dados).status_code, 302)
        self.assertEqual(Pagamento.objects.get().status, "aprovado")

    def test_proprietario_e_terceiro_nao_pagam_reserva_alheia(self):
        reserva = self.criar_reserva()
        url = reverse("pagamentos:pagar", args=[reserva.pk])
        for usuario in (self.proprietario, self.outro):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(url).status_code, 404)
                response = self.client.post(url, {
                    "meio": "pix", "resultado": "aprovado",
                })
                self.assertEqual(response.status_code, 404)
                self.assertFalse(Pagamento.objects.exists())

    def test_reservas_nao_aceitas_bloqueiam_get_post_e_servico(self):
        self.client.force_login(self.locatario)
        statuses = (
            Reserva.Status.SOLICITADA, Reserva.Status.RECUSADA,
            Reserva.Status.CANCELADA, Reserva.Status.EM_ANDAMENTO,
            Reserva.Status.CONCLUIDA,
        )
        for indice, status in enumerate(statuses):
            with self.subTest(status=status):
                reserva = self.criar_reserva(
                    status=status, inicio_dias=5 + indice * 10,
                )
                url = reverse("pagamentos:pagar", args=[reserva.pk])
                for response in (
                    self.client.get(url),
                    self.client.post(url, {
                        "meio": "pix", "resultado": "aprovado",
                    }),
                ):
                    self.assertRedirects(
                        response,
                        reverse("reservas:detalhe", args=[reserva.pk]),
                    )
                with self.assertRaises(PagamentoInvalido):
                    simular_pagamento(
                        reserva=reserva, meio="pix", resultado="aprovado",
                    )
                self.assertFalse(Pagamento.objects.exists())

    def test_campos_adulterados_nao_alteram_participante_ou_valores(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)
        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]), {
                "meio": "cartao", "resultado": "aprovado",
                "valor_bruto": "1.00", "total": "1.00", "comissao": "0.01",
                "repasse_proprietario": "0.99", "percentual_comissao": "0.00",
                "locatario": self.outro.pk, "reserva": "999999",
            },
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        pagamento = Pagamento.objects.get(reserva=reserva)
        self.assertEqual(pagamento.meio, Pagamento.Meio.CARTAO)
        self.assertEqual(pagamento.valor_bruto, reserva.total)
        self.assertEqual(pagamento.comissao, reserva.comissao)
        self.assertEqual(pagamento.repasse_proprietario, reserva.repasse_proprietario)

    def test_recusa_nova_tentativa_e_duplicacao_pela_view(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)
        url = reverse("pagamentos:pagar", args=[reserva.pk])
        self.client.post(url, {"meio": "cartao", "resultado": "recusado"})
        pagamento = Pagamento.objects.get(reserva=reserva)
        self.assertEqual(pagamento.status, Pagamento.Status.RECUSADO)
        response = self.client.get(url)
        self.assertContains(response, "Última tentativa")
        self.assertContains(response, "Recusado")

        self.client.post(url, {"meio": "pix", "resultado": "aprovado"})
        self.client.post(url, {"meio": "cartao", "resultado": "recusado"})
        pagamento.refresh_from_db()
        self.assertEqual(Pagamento.objects.count(), 1)
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        self.assertEqual(pagamento.meio, Pagamento.Meio.PIX)

    def test_formulario_invalido_nao_modifica_tentativa_recusada(self):
        reserva = self.criar_reserva()
        pagamento = simular_pagamento(
            reserva=reserva, meio="pix", resultado="recusado",
        )
        self.client.force_login(self.locatario)
        for dados in (
            {}, {"meio": "boleto", "resultado": "aprovado"},
            {"meio": "pix", "resultado": "invalido"},
        ):
            with self.subTest(dados=dados):
                response = self.client.post(
                    reverse("pagamentos:pagar", args=[reserva.pk]), dados,
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                pagamento.refresh_from_db()
                self.assertEqual(pagamento.status, Pagamento.Status.RECUSADO)
                self.assertEqual(Pagamento.objects.count(), 1)

    def test_cancelamento_pela_view_estorna_e_preserva_valores(self):
        reserva = self.criar_reserva()
        pagamento = simular_pagamento(
            reserva=reserva, meio="pix", resultado="aprovado",
        )
        self.client.force_login(self.locatario)
        response = self.client.post(reverse("reservas:cancelar", args=[reserva.pk]))

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        pagamento.refresh_from_db()
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)
        self.assertEqual(pagamento.status, Pagamento.Status.ESTORNADO)
        self.assertEqual(pagamento.valor_bruto, reserva.total)
        self.assertEqual(pagamento.comissao, reserva.comissao)
        self.assertEqual(pagamento.repasse_proprietario, reserva.repasse_proprietario)
        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]),
            {"meio": "pix", "resultado": "aprovado"},
        )
        self.assertEqual(response.status_code, 302)
        pagamento.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.Status.ESTORNADO)
        self.assertEqual(Pagamento.objects.count(), 1)

    def test_locatario_abre_formulario_de_pagamento(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)

        response = self.client.get(reverse("pagamentos:pagar", args=[reserva.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pagamentos/pagar.html")
        self.assertContains(response, "Pagamento da reserva")

    def test_locatario_aprova_pagamento(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]),
            {"meio": Pagamento.Meio.PIX, "resultado": "aprovado"},
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        pagamento = Pagamento.objects.get(reserva=reserva)
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)

    def test_outro_usuario_nao_paga_reserva_alheia(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.outro)

        response = self.client.get(reverse("pagamentos:pagar", args=[reserva.pk]))

        self.assertEqual(response.status_code, 404)

    def test_reserva_ja_paga_nao_abre_novo_pagamento(self):
        reserva = self.criar_reserva()
        simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )
        self.client.force_login(self.locatario)

        response = self.client.get(reverse("pagamentos:pagar", args=[reserva.pk]))

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        self.assertEqual(Pagamento.objects.count(), 1)
