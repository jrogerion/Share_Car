from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
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
    def test_servico_rejeita_notas_invalidas_sem_gravar(self):
        reserva = self.criar_reserva()
        for nota in (0, 6, -1, 2.5, True, "5", None):
            with self.subTest(nota=nota):
                with self.assertRaises(AvaliacaoInvalida):
                    avaliar_reserva(reserva=reserva, autor=self.locatario, nota=nota)
                self.assertFalse(Avaliacao.objects.exists())

    def test_autoavaliacao_bloqueada_antes_de_chegar_ao_banco(self):
        reserva = self.criar_reserva()
        Reserva.objects.filter(pk=reserva.pk).update(locatario=self.proprietario)
        reserva.refresh_from_db()

        self.assertFalse(pode_avaliar(reserva, self.proprietario))
        with self.assertRaises(AvaliacaoInvalida):
            avaliar_reserva(reserva=reserva, autor=self.proprietario, nota=5)
        self.assertFalse(Avaliacao.objects.exists())

    def test_servico_revalida_status_da_instancia(self):
        reserva = self.criar_reserva()
        Reserva.objects.filter(pk=reserva.pk).update(status=Reserva.Status.ACEITA)

        with self.assertRaises(AvaliacaoInvalida):
            avaliar_reserva(reserva=reserva, autor=self.locatario, nota=5)
        self.assertFalse(Avaliacao.objects.exists())

    def test_media_nao_revela_nota_antes_da_contraparte_avaliar(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.locatario, nota=1)

        self.assertEqual(
            resumo_avaliacoes_veiculo(self.veiculo), {"media": None, "total": 0},
        )
        avaliar_reserva(reserva=reserva, autor=self.proprietario, nota=5)
        self.assertEqual(
            resumo_avaliacoes_veiculo(self.veiculo), {"media": 1.0, "total": 1},
        )

    def test_media_ignora_reserva_com_nota_ainda_oculta(self):
        primeira = self.criar_reserva()
        segunda = self.criar_reserva(dias_inicio=20)
        avaliar_reserva(reserva=primeira, autor=self.locatario, nota=5)
        avaliar_reserva(reserva=primeira, autor=self.proprietario, nota=4)
        avaliar_reserva(reserva=segunda, autor=self.locatario, nota=1)

        self.assertEqual(
            resumo_avaliacoes_veiculo(self.veiculo), {"media": 5.0, "total": 1},
        )

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
        avaliar_reserva(reserva=primeira, autor=self.proprietario, nota=2)
        avaliar_reserva(reserva=segunda, autor=self.proprietario, nota=4)

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
    def test_visitante_e_terceiro_nao_enviam_avaliacoes(self):
        reserva = self.criar_reserva()
        url = reverse("avaliacoes:avaliar", args=[reserva.pk])
        for metodo in (self.client.get, self.client.post):
            self.assertEqual(metodo(url).status_code, 302)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.post(url, {"nota": 5}).status_code, 404)
        self.assertFalse(Avaliacao.objects.exists())

    def test_get_e_post_bloqueados_em_reservas_nao_concluidas(self):
        self.client.force_login(self.locatario)
        statuses = (
            Reserva.Status.SOLICITADA, Reserva.Status.ACEITA,
            Reserva.Status.RECUSADA, Reserva.Status.CANCELADA,
            Reserva.Status.EM_ANDAMENTO,
        )
        for indice, status in enumerate(statuses):
            reserva = self.criar_reserva(dias_inicio=5 + indice * 10, status=status)
            url = reverse("avaliacoes:avaliar", args=[reserva.pk])
            for response in (
                self.client.get(url), self.client.post(url, {"nota": "5"}),
                self.client.post(url, {"nota": "invalida"}),
            ):
                self.assertRedirects(
                    response, reverse("reservas:detalhe", args=[reserva.pk]),
                )
        self.assertFalse(Avaliacao.objects.exists())

    def test_post_ignora_autor_avaliado_e_reserva_forjados(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.proprietario)
        response = self.client.post(
            reverse("avaliacoes:avaliar", args=[reserva.pk]), {
                "nota": "1", "autor": self.outro.pk,
                "avaliado": self.proprietario.pk, "reserva": "999999",
            },
        )
        self.assertEqual(response.status_code, 302)
        avaliacao = Avaliacao.objects.get()
        self.assertEqual(avaliacao.autor_id, self.proprietario.pk)
        self.assertEqual(avaliacao.avaliado_id, self.locatario.pk)
        self.assertEqual(avaliacao.reserva_id, reserva.pk)

    def test_notas_invalidas_nao_gravam_e_duplicacao_nao_altera_nota(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)
        url = reverse("avaliacoes:avaliar", args=[reserva.pk])
        for nota in ("0", "6", "2.5", "", "<script>"):
            response = self.client.post(url, {"nota": nota})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertFalse(Avaliacao.objects.exists())
        self.client.post(url, {"nota": "5"})
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(url, {"nota": "1"}).status_code, 302)
        self.assertEqual(Avaliacao.objects.count(), 1)
        self.assertEqual(Avaliacao.objects.get().nota, 5)

    def test_nota_oculta_nao_e_exposta_no_contexto_do_formulario(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.proprietario, nota=1)
        self.client.force_login(self.locatario)
        url = reverse("avaliacoes:avaliar", args=[reserva.pk])
        for response in (self.client.get(url), self.client.post(url, {"nota": "0"})):
            self.assertTrue(response.context["outra_parte_avaliou"])
            self.assertIsNone(response.context["avaliacao_outra_parte"])
            self.assertNotContains(response, "1/5")

    def test_anuncio_nao_revela_media_oculta_para_nenhum_usuario(self):
        reserva = self.criar_reserva()
        avaliar_reserva(reserva=reserva, autor=self.locatario, nota=1)
        for usuario in (None, self.proprietario, self.locatario, self.outro):
            self.client.logout()
            if usuario:
                self.client.force_login(usuario)
            response = self.client.get(
                reverse("core:detalhes", args=[self.veiculo.pk]),
            )
            self.assertEqual(response.context["avaliacoes"]["total"], 0)
            self.assertNotContains(response, "Nota média")

    def test_formulario_sem_cache_e_protecao_csrf(self):
        reserva = self.criar_reserva()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.locatario)
        url = reverse("avaliacoes:avaliar", args=[reserva.pk])
        response = client.get(url)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(client.post(url, {"nota": "5"}).status_code, 403)
        self.assertFalse(Avaliacao.objects.exists())
        response = client.post(url, {
            "nota": "5", "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Avaliacao.objects.get().nota, 5)

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
        avaliar_reserva(reserva=reserva, autor=self.proprietario, nota=4)

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
