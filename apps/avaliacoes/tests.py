from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Usuario
from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .models import Avaliacao
from .services import (
    AvaliacaoInvalida,
    avaliar_reserva,
    pode_avaliar,
    resumo_avaliacoes_veiculo,
)


class AvaliacaoBaseTests(TestCase):
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

    def criar_reserva(self, *, dias_inicio=5, status=Reserva.Status.CONCLUIDA):
        inicio = timezone.localdate() + timedelta(days=dias_inicio)
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
            percentual_comissao=Decimal("15.00"),
        )


class AvaliacaoServiceTests(AvaliacaoBaseTests):
    def test_locatario_avalia_proprietario(self):
        reserva = self.criar_reserva()

        avaliacao = avaliar_reserva(
            reserva=reserva,
            autor=self.locatario,
            nota=5,
        )

        self.assertEqual(avaliacao.avaliado, self.proprietario)
        self.assertEqual(avaliacao.nota, 5)

    def test_proprietario_avalia_locatario(self):
        reserva = self.criar_reserva()

        avaliacao = avaliar_reserva(
            reserva=reserva,
            autor=self.proprietario,
            nota=4,
        )

        self.assertEqual(avaliacao.avaliado, self.locatario)

    def test_avaliacao_exige_locacao_concluida(self):
        reserva = self.criar_reserva(status=Reserva.Status.EM_ANDAMENTO)

        with self.assertRaises(AvaliacaoInvalida):
            avaliar_reserva(reserva=reserva, autor=self.locatario, nota=5)

    def test_usuario_de_fora_nao_avalia(self):
        reserva = self.criar_reserva()

        with self.assertRaises(AvaliacaoInvalida):
            avaliar_reserva(reserva=reserva, autor=self.outro, nota=5)

    def test_cada_parte_avalia_uma_unica_vez(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.locatario, nota=5)

        with self.assertRaises(AvaliacaoInvalida):
            avaliar_reserva(reserva=reserva, autor=self.locatario, nota=4)

    def test_pode_avaliar_reflete_estado_da_reserva(self):
        reserva = self.criar_reserva()

        self.assertTrue(pode_avaliar(reserva, self.locatario))
        avaliar_reserva(reserva=reserva, autor=self.locatario, nota=5)
        self.assertFalse(pode_avaliar(reserva, self.locatario))
        self.assertTrue(pode_avaliar(reserva, self.proprietario))

    def test_media_do_veiculo_considera_avaliacoes_dos_locatarios(self):
        primeira = self.criar_reserva()
        segunda = self.criar_reserva(dias_inicio=20)
        avaliar_reserva(reserva=primeira, autor=self.locatario, nota=5)
        avaliar_reserva(reserva=segunda, autor=self.locatario, nota=3)

        resumo = resumo_avaliacoes_veiculo(self.veiculo)

        self.assertEqual(resumo["total"], 2)
        self.assertEqual(resumo["media"], Decimal("4.0"))

    def test_media_do_veiculo_ignora_avaliacoes_do_proprietario(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.proprietario, nota=1)

        resumo = resumo_avaliacoes_veiculo(self.veiculo)

        self.assertEqual(resumo["total"], 0)
        self.assertIsNone(resumo["media"])


class AvaliarReservaViewTests(AvaliacaoBaseTests):
    def test_locatario_abre_formulario_de_avaliacao(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)

        response = self.client.get(reverse("avaliacoes:avaliar", args=[reserva.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "avaliacoes/avaliar.html")
        self.assertContains(response, "Avaliar proprietario")

    def test_locatario_envia_avaliacao(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("avaliacoes:avaliar", args=[reserva.pk]),
            {"nota": "5"},
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        avaliacao = Avaliacao.objects.get(reserva=reserva, autor=self.locatario)
        self.assertEqual(avaliacao.nota, 5)

    def test_avaliacoes_ficam_ocultas_ate_as_duas_partes_avaliarem(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.proprietario, nota=4)
        self.client.force_login(self.locatario)

        response = self.client.get(
            reverse("reservas:detalhe", args=[reserva.pk])
        )

        self.assertContains(response, "A outra parte já avaliou")
        self.assertNotContains(response, "Nota da outra parte")

        self.client.post(
            reverse("avaliacoes:avaliar", args=[reserva.pk]),
            {"nota": "5"},
        )
        response = self.client.get(
            reverse("reservas:detalhe", args=[reserva.pk])
        )

        self.assertContains(response, "Nota da outra parte")
        self.assertContains(response, "4/5")
        self.assertContains(response, "5/5")

    def test_media_aparece_no_anuncio_do_veiculo(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.locatario, nota=5)

        response = self.client.get(
            reverse("core:detalhes", args=[self.veiculo.pk])
        )

        self.assertEqual(response.context["avaliacoes"]["media"], Decimal("5.0"))
        self.assertContains(response, "Nota média")

    def test_usuario_de_fora_nao_abre_avaliacao(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.outro)

        response = self.client.get(reverse("avaliacoes:avaliar", args=[reserva.pk]))

        self.assertEqual(response.status_code, 404)
