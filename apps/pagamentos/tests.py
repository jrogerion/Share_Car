from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
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
        self,
        *,
        status=Reserva.Status.ACEITA,
        inicio_dias=5,
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
        self.assertEqual(pagamento.comissao, reserva.comissao)
        self.assertEqual(
            pagamento.repasse_proprietario,
            reserva.repasse_proprietario,
        )
        self.assertEqual(
            pagamento.comissao + pagamento.repasse_proprietario,
            pagamento.valor_bruto,
        )

    def test_pagamento_respeita_percentual_de_comissao_da_reserva(self):
        reserva = self.criar_reserva(
            percentual_comissao=Decimal("10.00"),
        )

        pagamento = simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )

        self.assertEqual(pagamento.valor_bruto, Decimal("450.00"))
        self.assertEqual(pagamento.comissao, Decimal("45.00"))
        self.assertEqual(pagamento.repasse_proprietario, Decimal("405.00"))
        self.assertEqual(
            pagamento.comissao + pagamento.repasse_proprietario,
            pagamento.valor_bruto,
        )

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
        self.assertEqual(pagamento.valor_bruto, reserva.total)
        self.assertEqual(pagamento.comissao, reserva.comissao)
        self.assertEqual(
            pagamento.repasse_proprietario,
            reserva.repasse_proprietario,
        )

    def test_pagamento_aprovado_com_cartao_pela_view(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]),
            {"meio": Pagamento.Meio.CARTAO, "resultado": "aprovado"},
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        pagamento = Pagamento.objects.get(reserva=reserva)
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        self.assertEqual(pagamento.meio, Pagamento.Meio.CARTAO)

    def test_outro_usuario_nao_paga_reserva_alheia(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.outro)

        response = self.client.get(reverse("pagamentos:pagar", args=[reserva.pk]))

        self.assertEqual(response.status_code, 404)

    def test_outro_usuario_nao_paga_reserva_alheia_por_post(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.outro)

        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]),
            {"meio": Pagamento.Meio.PIX, "resultado": "aprovado"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Pagamento.objects.filter(reserva=reserva).exists())

    def test_proprietario_nao_paga_reserva_do_proprio_veiculo(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.proprietario)
        url = reverse("pagamentos:pagar", args=[reserva.pk])

        with self.subTest(metodo="GET"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        with self.subTest(metodo="POST"):
            response = self.client.post(
                url,
                {"meio": Pagamento.Meio.PIX, "resultado": "aprovado"},
            )
            self.assertEqual(response.status_code, 404)

        self.assertFalse(Pagamento.objects.filter(reserva=reserva).exists())

    def test_reservas_nao_aceitas_nao_permitem_pagamento_pela_view(self):
        statuses = (
            Reserva.Status.SOLICITADA,
            Reserva.Status.RECUSADA,
            Reserva.Status.CANCELADA,
            Reserva.Status.EM_ANDAMENTO,
            Reserva.Status.CONCLUIDA,
        )
        self.client.force_login(self.locatario)

        for indice, status in enumerate(statuses):
            with self.subTest(status=status):
                reserva = self.criar_reserva(
                    status=status,
                    inicio_dias=5 + indice * 10,
                )
                url = reverse("pagamentos:pagar", args=[reserva.pk])

                get_response = self.client.get(url)
                self.assertRedirects(
                    get_response,
                    reverse("reservas:detalhe", args=[reserva.pk]),
                )

                post_response = self.client.post(
                    url,
                    {"meio": Pagamento.Meio.PIX, "resultado": "aprovado"},
                )
                self.assertRedirects(
                    post_response,
                    reverse("reservas:detalhe", args=[reserva.pk]),
                )

                self.assertFalse(
                    Pagamento.objects.filter(reserva=reserva).exists()
                )

    def test_campos_adulterados_de_valor_sao_ignorados(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]),
            {
                "meio": Pagamento.Meio.PIX,
                "resultado": "aprovado",
                "valor_bruto": "1.00",
                "comissao": "0.01",
                "repasse_proprietario": "0.99",
                "total": "1.00",
                "percentual_comissao": "0.00",
            },
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        pagamento = Pagamento.objects.get(reserva=reserva)
        self.assertEqual(pagamento.valor_bruto, reserva.total)
        self.assertEqual(pagamento.comissao, reserva.comissao)
        self.assertEqual(
            pagamento.repasse_proprietario,
            reserva.repasse_proprietario,
        )
        self.assertNotEqual(pagamento.valor_bruto, Decimal("1.00"))

    def test_pagamento_recusado_permite_nova_tentativa_pela_view(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)
        url = reverse("pagamentos:pagar", args=[reserva.pk])

        primeira = self.client.post(
            url,
            {"meio": Pagamento.Meio.CARTAO, "resultado": "recusado"},
        )
        self.assertRedirects(
            primeira,
            reverse("reservas:detalhe", args=[reserva.pk]),
        )
        pagamento = Pagamento.objects.get(reserva=reserva)
        self.assertEqual(pagamento.status, Pagamento.Status.RECUSADO)

        segunda = self.client.post(
            url,
            {"meio": Pagamento.Meio.PIX, "resultado": "aprovado"},
        )
        self.assertRedirects(
            segunda,
            reverse("reservas:detalhe", args=[reserva.pk]),
        )
        self.assertEqual(Pagamento.objects.count(), 1)
        pagamento.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        self.assertEqual(pagamento.meio, Pagamento.Meio.PIX)

    def test_cancelamento_pela_view_estorna_pagamento_aprovado(self):
        reserva = self.criar_reserva()
        pagamento = simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("reservas:cancelar", args=[reserva.pk]),
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        reserva.refresh_from_db()
        pagamento.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)
        self.assertEqual(pagamento.status, Pagamento.Status.ESTORNADO)
        self.assertEqual(Pagamento.objects.count(), 1)

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

    def test_reserva_ja_paga_nao_permite_novo_post(self):
        reserva = self.criar_reserva()
        pagamento = simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("pagamentos:pagar", args=[reserva.pk]),
            {"meio": Pagamento.Meio.CARTAO, "resultado": "aprovado"},
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        self.assertEqual(Pagamento.objects.count(), 1)
        pagamento.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        self.assertEqual(pagamento.meio, Pagamento.Meio.PIX)
