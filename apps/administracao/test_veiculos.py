from unittest.mock import patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.test import Client, TestCase
from django.urls import reverse

from apps.contas.models import Usuario
from apps.veiculos.consultas import veiculos_publicos
from apps.veiculos.models import FotoVeiculo, Veiculo


class AnalisePublicacaoVeiculoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            "operador-veiculos", "operador@example.com", is_staff=True,
        )
        cls.dono = Usuario.objects.create_user(
            "proprietario", "dono@example.com", first_name="Pessoa",
            proprietario=True,
        )
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.dono,
            caracteristicas="Descrição completa para análise",
            cidade="Maria da Fé", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="150.00",
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse(
            "administracao:analise_veiculo", args=[self.veiculo.pk],
        )
        self.aprovar = reverse(
            "administracao:veiculo", args=[self.veiculo.pk, "aprovar"],
        )
        self.rejeitar = reverse(
            "administracao:veiculo", args=[self.veiculo.pk, "rejeitar"],
        )
        self.bloquear = reverse(
            "administracao:bloqueio_veiculo", args=[self.veiculo.pk],
        )

    def test_painel_oferece_acesso_a_analise(self):
        response = self.client.get(reverse("administracao:painel"))
        self.assertContains(response, f'href="{self.url}"')

    def test_administrador_consulta_dados_e_fotos_de_pendente(self):
        with patch.object(
            FotoVeiculo._meta.get_field("foto"), "storage", InMemoryStorage(),
        ):
            foto = FotoVeiculo.objects.create(
                veiculo=self.veiculo,
                foto=ContentFile(b"fixture de teste", name="foto.png"),
            )
            response = self.client.get(self.url)
            self.assertContains(response, self.veiculo.caracteristicas)
            self.assertContains(response, "Maria da Fé")
            self.assertContains(response, "Pessoa")
            self.assertContains(response, f'src="{foto.foto.url}"')
            self.assertContains(
                response, "Aguardando aprovação administrativa.",
            )
            self.assertIn("no-store", response["Cache-Control"])

    def test_analise_sem_fotos_e_veiculo_inexistente(self):
        self.assertContains(
            self.client.get(self.url), "Nenhuma foto cadastrada.",
        )
        response = self.client.get(reverse(
            "administracao:analise_veiculo", args=[999999],
        ))
        self.assertEqual(response.status_code, 404)

    def test_anonimo_e_usuario_comum_nao_acessam_analise_ou_decisoes(self):
        for usuario in (None, self.dono):
            with self.subTest(usuario=usuario):
                self.client.logout()
                if usuario:
                    self.client.force_login(usuario)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 302)
                for url in (self.aprovar, self.rejeitar, self.bloquear):
                    self.assertEqual(self.client.post(url).status_code, 302)
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "pendente")
        self.assertFalse(self.veiculo.bloqueado)

    def test_aprovar_publica_e_rejeitar_remove_da_busca(self):
        self.client.post(self.aprovar)
        self.assertTrue(
            veiculos_publicos().filter(pk=self.veiculo.pk).exists(),
        )
        self.client.post(self.rejeitar)
        self.assertFalse(
            veiculos_publicos().filter(pk=self.veiculo.pk).exists(),
        )
        self.assertEqual(LogEntry.objects.filter(
            user_id=self.admin.pk, object_id=str(self.veiculo.pk),
            action_flag=CHANGE,
        ).count(), 2)

    def test_aprovar_nao_remove_bloqueio_nem_ativa_anuncio(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(
            ativo=False, bloqueado=True,
        )
        self.client.post(self.aprovar)
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "aprovado")
        self.assertFalse(self.veiculo.ativo)
        self.assertTrue(self.veiculo.bloqueado)
        self.assertFalse(
            veiculos_publicos().filter(pk=self.veiculo.pk).exists(),
        )

    def test_bloquear_remove_e_desbloquear_preserva_aprovacao(self):
        self.client.post(self.aprovar)
        self.client.post(self.bloquear)
        self.assertFalse(
            veiculos_publicos().filter(pk=self.veiculo.pk).exists(),
        )
        self.client.post(self.bloquear)
        self.assertTrue(
            veiculos_publicos().filter(pk=self.veiculo.pk).exists(),
        )
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "aprovado")

    def test_desbloquear_pendente_nao_publica(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(bloqueado=True)
        self.client.post(self.bloquear)
        self.assertFalse(
            veiculos_publicos().filter(pk=self.veiculo.pk).exists(),
        )

    def test_decisoes_por_get_e_posts_sem_csrf_nao_alteram_dados(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url in (self.aprovar, self.rejeitar, self.bloquear):
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(client.post(url).status_code, 403)
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "pendente")
        self.assertFalse(self.veiculo.bloqueado)

    def test_decisao_invalida_nao_registra_alteracao(self):
        response = self.client.post(reverse(
            "administracao:veiculo", args=[self.veiculo.pk, "invalida"],
        ))
        self.assertRedirects(response, reverse("administracao:painel"))
        self.assertFalse(LogEntry.objects.filter(action_flag=CHANGE).exists())
