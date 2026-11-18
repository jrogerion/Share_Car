from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.contas.forms import DocumentoIdentidadeForm
from apps.contas.models import Usuario
from apps.locacoes.models import FotoRegistroLocacao
from apps.locacoes.services import registrar_locacao
from apps.pagamentos.services import simular_pagamento
from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo


def foto_com_metadados():
    buffer = BytesIO()
    exif = Image.Exif()
    exif[270] = "METADADO-FICTICIO-DE-TESTE"
    exif[274] = 6
    Image.new("RGB", (4, 2), "blue").save(buffer, format="JPEG", exif=exif)
    return SimpleUploadedFile(
        "nome-pessoal-ficticio.jpg", buffer.getvalue() + b"MARCADOR-EXTRA-FICTICIO",
        content_type="image/jpeg",
    )


class AuditoriaSegurancaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = Usuario.objects.create_user("staff-auditoria", is_staff=True)
        cls.superuser = Usuario.objects.create_user("super-auditoria", is_staff=True, is_superuser=True)
        cls.dono = Usuario.objects.create_user("dono-auditoria")
        cls.cliente = Usuario.objects.create_user("cliente-auditoria", locatario=True)

    def setUp(self):
        for model, campo in ((Usuario, "documento_identidade"), (FotoRegistroLocacao, "foto")):
            self.enterContext(patch.object(model._meta.get_field(campo), "storage", InMemoryStorage()))

    def test_staff_nao_bloqueia_nem_reativa_conta_privilegiada(self):
        self.client.force_login(self.staff)
        for alvo in (self.superuser, Usuario.objects.create_user("outro-staff-auditoria", is_staff=True)):
            for ativo in (True, False):
                with self.subTest(alvo=alvo.pk, ativo=ativo):
                    Usuario.objects.filter(pk=alvo.pk).update(is_active=ativo)
                    self.client.post(reverse("administracao:bloqueio_usuario", args=[alvo.pk]))
                    alvo.refresh_from_db()
                    self.assertEqual(alvo.is_active, ativo)

    def test_superusuario_ainda_pode_gerenciar_staff(self):
        self.client.force_login(self.superuser)
        url = reverse("administracao:bloqueio_usuario", args=[self.staff.pk])
        self.client.post(url)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.client.post(url)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_bloqueio_administrativo_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        response = client.post(reverse("administracao:bloqueio_usuario", args=[self.staff.pk]))
        self.assertEqual(response.status_code, 403)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_login_nao_redireciona_para_dominio_externo(self):
        usuario = Usuario.objects.create_user(
            "login-auditoria", "login-auditoria@example.com", "SenhaTeste!12345",
        )
        response = self.client.post(reverse("core:entrar"), {
            "username": usuario.email, "password": "SenhaTeste!12345",
            "next": "https://externo.example/roubar-sessao",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/"))
        self.assertNotIn("externo.example", response.url)

    def test_perfil_ignora_injecao_de_privilegios_e_aprovacoes(self):
        self.client.force_login(self.cliente)
        response = self.client.post(reverse("contas:perfil"), {
            "first_name": "Cliente", "last_name": "Fictício", "locatario": "on",
            "is_staff": "on", "is_superuser": "on", "is_active": "",
            "aprovacao_documento": "aprovado", "aprovacao_cnh": "aprovado",
            "email": "intruso@example.com", "username": "identificador-adulterado",
        })
        self.assertEqual(response.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.conta_administrativa)
        self.assertTrue(self.cliente.is_active)
        self.assertEqual(self.cliente.aprovacao_documento, "pendente")
        self.assertEqual(self.cliente.aprovacao_cnh, "pendente")
        self.assertEqual(self.cliente.email, "")
        self.assertEqual(self.cliente.username, "cliente-auditoria")

    def test_documento_remove_metadados_e_conteudo_extra(self):
        form = DocumentoIdentidadeForm(
            {}, {"documento_identidade": foto_com_metadados()}, instance=self.cliente,
        )
        self.assertTrue(form.is_valid(), form.errors)
        arquivo = form.cleaned_data["documento_identidade"]
        conteudo = arquivo.read()
        self.assertNotIn(b"MARCADOR-EXTRA-FICTICIO", conteudo)
        with Image.open(BytesIO(conteudo)) as imagem:
            self.assertFalse(imagem.getexif())
            self.assertEqual(imagem.size, (2, 4))

    def test_documento_rejeita_imagem_acima_de_20_megapixels(self):
        buffer = BytesIO()
        Image.new("RGB", (5000, 4001)).save(buffer, format="PNG")
        form = DocumentoIdentidadeForm({}, {
            "documento_identidade": SimpleUploadedFile("grande.png", buffer.getvalue(), content_type="image/png"),
        }, instance=self.cliente)
        self.assertFalse(form.is_valid())
        self.assertIn("20 megapixels", str(form.errors))

    def test_vistoria_nova_remove_metadados_e_anonimiza_nome(self):
        veiculo = Veiculo.objects.create(
            proprietario=self.dono, cidade="Campinas", categoria="Hatch",
            caracteristicas="Fictício", cambio="Manual", combustivel="Flex",
            passageiros=5, preco_diaria="150.00", aprovacao="aprovado",
        )
        inicio = timezone.localdate() + timedelta(days=5)
        reserva = Reserva.objects.create(
            veiculo=veiculo, locatario=self.cliente, inicio=inicio,
            fim=inicio + timedelta(days=1), status="aceita", preco_diaria="150.00",
            valor_diarias="150.00", total="150.00", taxas=0, percentual_comissao="15.00",
        )
        simular_pagamento(reserva=reserva, meio="pix", resultado="aprovado")
        registro = registrar_locacao(
            reserva=reserva, tipo="check_in", quilometragem=100,
            nivel_combustivel=50, fotos=[foto_com_metadados()],
        )
        foto = registro.fotos.get()
        self.assertRegex(foto.foto.name, r"^locacoes/[a-f0-9]{32}\.jpg$")
        with foto.foto.open("rb") as arquivo:
            conteudo = arquivo.read()
        self.assertNotIn(b"MARCADOR-EXTRA-FICTICIO", conteudo)
        with Image.open(BytesIO(conteudo)) as imagem:
            self.assertFalse(imagem.getexif())
            self.assertEqual(imagem.size, (2, 4))
