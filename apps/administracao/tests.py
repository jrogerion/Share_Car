from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Usuario
from apps.veiculos.models import Veiculo

from .models import ConfiguracaoComissao


class AdministracaoBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="senha-de-teste",
            is_staff=True,
        )
        cls.usuario = Usuario.objects.create_user(
            username="usuario",
            email="usuario@example.com",
            password="senha-de-teste",
            documento_identidade="identidades/documento.pdf",
            cnh_numero="123456789",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.outro = Usuario.objects.create_user(
            username="outro",
            email="outro@example.com",
            password="senha-de-teste",
        )
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.outro,
            caracteristicas="Veículo de teste",
            cidade="São Paulo",
            categoria="Hatch",
            cambio="Manual",
            combustivel="Flex",
            passageiros=5,
            preco_diaria=Decimal("150.00"),
            ativo=True,
            bloqueado=False,
            aprovacao=Veiculo.Aprovacao.PENDENTE,
        )


class AcessoAdministracaoTests(AdministracaoBaseTests):
    def test_anonimo_e_redirecionado_para_entrar(self):
        response = self.client.get(reverse("administracao:painel"))

        self.assertRedirects(
            response,
            f"{reverse('core:entrar')}?next={reverse('administracao:painel')}",
        )

    def test_usuario_comum_nao_acessa_administracao(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("administracao:painel"))

        self.assertRedirects(response, reverse("contas:painel"))

    def test_staff_acessa_painel(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("administracao:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "administracao/painel.html")
        self.assertContains(response, "Painel administrativo")


class AprovacaoTests(AdministracaoBaseTests):
    def setUp(self):
        self.admin.is_superuser = True
        self.admin.save(update_fields=["is_superuser"])
        storage_patch = patch.object(
            Usuario._meta.get_field("documento_identidade"),
            "storage", InMemoryStorage(),
        )
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        self.usuario.refresh_from_db()
        self.usuario.documento_identidade.save(
            "documento-ficticio.png", ContentFile(b"fixture privada de teste"),
        )
        self.client.force_login(self.admin)

    def test_staff_nao_pode_analisar_documento_ou_cnh(self):
        self.admin.is_superuser = False
        self.admin.save(update_fields=["is_superuser"])
        for rota in ("documento", "cnh"):
            response = self.client.post(reverse(
                f"administracao:{rota}", args=[self.usuario.pk, "aprovar"],
            ))
            self.assertRedirects(response, reverse("contas:painel"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.aprovacao_documento, "pendente")
        self.assertEqual(self.usuario.aprovacao_cnh, "pendente")

    def test_cnh_vencida_nao_pode_ser_aprovada(self):
        self.usuario.cnh_validade = timezone.localdate() - timedelta(days=1)
        self.usuario.save(update_fields=["cnh_validade"])
        self.client.post(reverse(
            "administracao:cnh", args=[self.usuario.pk, "aprovar"],
        ))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.aprovacao_cnh, "pendente")

    def test_nao_aprova_documento_com_arquivo_inexistente(self):
        self.usuario.documento_identidade.name = "identidades/inexistente.png"
        self.usuario.save(update_fields=["documento_identidade"])
        self.client.post(reverse(
            "administracao:documento", args=[self.usuario.pk, "aprovar"],
        ))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.aprovacao_documento, "pendente")

    def test_aprova_documento(self):
        response = self.client.post(
            reverse("administracao:documento", args=[self.usuario.pk, "aprovar"])
        )

        self.assertRedirects(response, reverse("administracao:painel"))
        self.usuario.refresh_from_db()
        self.assertEqual(
            self.usuario.aprovacao_documento,
            Usuario.Aprovacao.APROVADO,
        )
        self.assertTrue(LogEntry.objects.filter(
            user_id=self.admin.pk, object_id=str(self.usuario.pk),
        ).exists())

    def test_rejeita_cnh(self):
        response = self.client.post(
            reverse("administracao:cnh", args=[self.usuario.pk, "rejeitar"])
        )

        self.assertRedirects(response, reverse("administracao:painel"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.aprovacao_cnh, Usuario.Aprovacao.REJEITADO)

    def test_nao_aprova_documento_ausente(self):
        self.client.post(
            reverse("administracao:documento", args=[self.outro.pk, "aprovar"])
        )

        self.outro.refresh_from_db()
        self.assertEqual(
            self.outro.aprovacao_documento,
            Usuario.Aprovacao.PENDENTE,
        )

    def test_aprova_veiculo(self):
        response = self.client.post(
            reverse("administracao:veiculo", args=[self.veiculo.pk, "aprovar"])
        )

        self.assertRedirects(response, reverse("administracao:painel"))
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, Veiculo.Aprovacao.APROVADO)


class BloqueioTests(AdministracaoBaseTests):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_bloqueia_e_reativa_usuario(self):
        self.client.post(
            reverse("administracao:bloqueio_usuario", args=[self.outro.pk])
        )
        self.outro.refresh_from_db()
        self.assertFalse(self.outro.is_active)

        self.client.post(
            reverse("administracao:bloqueio_usuario", args=[self.outro.pk])
        )
        self.outro.refresh_from_db()
        self.assertTrue(self.outro.is_active)

    def test_admin_nao_bloqueia_a_propria_conta(self):
        self.client.post(
            reverse("administracao:bloqueio_usuario", args=[self.admin.pk])
        )

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_bloqueia_e_desbloqueia_veiculo(self):
        self.client.post(
            reverse("administracao:bloqueio_veiculo", args=[self.veiculo.pk])
        )
        self.veiculo.refresh_from_db()
        self.assertTrue(self.veiculo.bloqueado)

        self.client.post(
            reverse("administracao:bloqueio_veiculo", args=[self.veiculo.pk])
        )
        self.veiculo.refresh_from_db()
        self.assertFalse(self.veiculo.bloqueado)


class ComissaoTests(AdministracaoBaseTests):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_atualiza_percentual_da_comissao(self):
        response = self.client.post(
            reverse("administracao:comissao"),
            {"percentual": "20.00"},
        )

        self.assertRedirects(response, reverse("administracao:painel"))
        configuracao = ConfiguracaoComissao.objects.get(pk=1)
        self.assertEqual(configuracao.percentual, Decimal("20.00"))

    def test_percentual_invalido_nao_e_salvo(self):
        response = self.client.post(
            reverse("administracao:comissao"),
            {"percentual": "101.00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "entre 0 e 100")
        configuracao = ConfiguracaoComissao.objects.get(pk=1)
        self.assertEqual(configuracao.percentual, Decimal("15.00"))

    def test_painel_mostra_pendencias(self):
        response = self.client.get(reverse("administracao:painel"))

        self.assertContains(response, "Documentos pendentes")
        self.assertContains(response, "Veículos pendentes")
        self.assertContains(response, self.usuario.username)
