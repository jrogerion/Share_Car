from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.avaliacoes.models import Avaliacao
from apps.contas.models import Usuario
from apps.locacoes.models import FotoRegistroLocacao, RegistroLocacao
from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva
from apps.veiculos.models import FotoVeiculo, Veiculo


class JornadaIntegradaTests(TestCase):
    """Exercita as URLs reais sem escrever em bancos ou arquivos do projeto."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser(
            "admin-jornada", "admin-jornada@example.com", "Senha-teste!12345",
        )
        cls.staff = Usuario.objects.create_user(
            "staff-jornada", "staff-jornada@example.com", is_staff=True,
        )
        cls.terceiro = Usuario.objects.create_user(
            "terceiro-jornada", "terceiro-jornada@example.com",
        )

    def setUp(self):
        for modelo, campo in (
            (Usuario, "documento_identidade"),
            (FotoVeiculo, "foto"), (FotoRegistroLocacao, "foto"),
        ):
            troca = patch.object(
                modelo._meta.get_field(campo), "storage", InMemoryStorage(),
            )
            troca.start()
            self.addCleanup(troca.stop)
        self.locatario = Client(enforce_csrf_checks=True)
        self.proprietario = Client(enforce_csrf_checks=True)
        self.administrador = Client(enforce_csrf_checks=True)
        self.administrador.force_login(self.admin)

    @staticmethod
    def imagem(nome="teste.png"):
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
        return SimpleUploadedFile(nome, buffer.getvalue(), "image/png")

    def enviar(self, client, rota, dados=None, args=None):
        if "csrftoken" not in client.cookies:
            rota_token = (
                "contas:perfil" if "_auth_user_id" in client.session
                else "core:entrar"
            )
            client.get(reverse(rota_token))
        return client.post(reverse(rota, args=args), {
            **(dados or {}),
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })

    def cadastrar(self, client, email, papel):
        response = self.enviar(client, "contas:cadastro", {
            "email": email, "first_name": "Pessoa", "last_name": "Fictícia",
            papel: "on", "password1": "Senha-teste!12345",
            "password2": "Senha-teste!12345",
        })
        self.assertRedirects(response, reverse("contas:cadastro_concluido"))
        usuario = Usuario.objects.get(email=email)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        response = self.enviar(client, "core:entrar", {
            "username": email, "password": "Senha-teste!12345",
        })
        self.assertRedirects(response, reverse("reservas:minhas"))
        return usuario

    def test_cadastro_ate_avaliacao_com_aprovacoes_e_csrf(self):
        dono = self.cadastrar(
            self.proprietario, "dono-jornada@example.com", "proprietario",
        )
        locatario = self.cadastrar(
            self.locatario, "locatario-jornada@example.com", "locatario",
        )
        response = self.enviar(self.proprietario, "contas:enviar_documento", {
            "documento_identidade": self.imagem("documento-ficticio.png"),
        })
        self.assertRedirects(response, reverse("contas:perfil"))
        self.assertRedirects(
            self.proprietario.get(reverse("core:veiculo")),
            reverse("contas:perfil"),
        )
        self.enviar(self.locatario, "contas:perfil", {
            "first_name": "Pessoa", "last_name": "Fictícia", "locatario": "on",
            "cnh_numero": "CNH-FICTICIA-TESTE",
            "cnh_validade": (
                timezone.localdate() + timedelta(days=365)
            ).isoformat(),
        })

        funcionario = Client(enforce_csrf_checks=True)
        funcionario.force_login(self.staff)
        self.enviar(
            funcionario, "administracao:documento", args=[dono.pk, "aprovar"],
        )
        dono.refresh_from_db()
        self.assertEqual(dono.aprovacao_documento, Usuario.Aprovacao.PENDENTE)
        for rota, usuario in (
            ("administracao:documento", dono),
            ("administracao:cnh", locatario),
        ):
            self.enviar(self.administrador, rota, args=[usuario.pk, "aprovar"])
        dono.refresh_from_db()
        locatario.refresh_from_db()
        self.assertEqual(dono.aprovacao_documento, Usuario.Aprovacao.APROVADO)
        self.assertEqual(locatario.aprovacao_cnh, Usuario.Aprovacao.APROVADO)

        response = self.enviar(self.proprietario, "core:veiculo", {
            "caracteristicas": "Carro fictício da jornada integrada",
            "cidade": "São Paulo", "categoria": "Hatch", "cambio": "Manual",
            "combustivel": "Flex", "passageiros": 5, "preco_diaria": "150.00",
            "aprovacao": "aprovado", "proprietario": self.terceiro.pk,
        })
        self.assertRedirects(response, reverse("veiculos:meus"))
        carro = Veiculo.objects.get()
        self.assertEqual(carro.proprietario_id, dono.pk)
        self.assertEqual(carro.aprovacao, Veiculo.Aprovacao.PENDENTE)
        self.assertEqual(self.client.get(
            reverse("core:detalhes", args=[carro.pk]),
        ).status_code, 404)
        self.enviar(self.proprietario, "veiculos:fotos", {
            "foto": self.imagem("capa.png"),
        }, args=[carro.pk])
        self.enviar(
            funcionario, "administracao:veiculo", args=[carro.pk, "aprovar"],
        )

        inicio = timezone.localdate() + timedelta(days=3)
        periodo = {
            "retirada": inicio.isoformat(),
            "devolucao": (inicio + timedelta(days=3)).isoformat(),
        }
        response = self.locatario.get(reverse("core:resultados"), {
            **periodo, "cidade": "sao paulo", "categoria": "Hatch",
        })
        self.assertEqual(list(response.context["veiculos"]), [carro])
        self.assertContains(response, carro.fotos.get().foto.url)
        response = self.enviar(
            self.locatario, "reservas:criar", periodo, args=[carro.pk],
        )
        reserva = Reserva.objects.get()
        self.assertRedirects(
            response, reverse("reservas:detalhe", args=[reserva.pk]),
        )
        self.assertEqual(reserva.total, 450)
        detalhe = reverse("reservas:detalhe", args=[reserva.pk])
        self.assertFalse(self.locatario.get(detalhe).context["pode_pagar"])
        self.enviar(self.proprietario, "reservas:aceitar", args=[reserva.pk])
        self.assertTrue(self.locatario.get(detalhe).context["pode_pagar"])

        for resultado in ("recusado", "aprovado"):
            self.enviar(self.locatario, "pagamentos:pagar", {
                "meio": "pix", "resultado": resultado, "total": "0.01",
            }, args=[reserva.pk])
        pagamento = Pagamento.objects.get()
        self.assertEqual(pagamento.valor_bruto, 450)
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        self.assertTrue(self.locatario.get(detalhe).context["pode_checkin"])
        for rota, km in (
            ("locacoes:check_in", 1000), ("locacoes:check_out", 1120),
        ):
            response = self.enviar(self.locatario, rota, {
                "quilometragem": km, "nivel_combustivel": 80,
                "fotos": [self.imagem("vistoria-ficticia.png")],
            }, args=[reserva.pk])
            self.assertRedirects(response, detalhe)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CONCLUIDA)
        self.assertEqual(RegistroLocacao.objects.count(), 2)
        self.assertFalse(self.locatario.get(detalhe).context["pode_cancelar"])

        self.enviar(
            self.locatario, "avaliacoes:avaliar", {"nota": 5}, args=[reserva.pk],
        )
        response = self.proprietario.get(detalhe)
        self.assertIsNone(response.context["avaliacao_outra_parte"])
        anuncio = reverse("core:detalhes", args=[carro.pk])
        self.assertEqual(
            self.client.get(anuncio).context["avaliacoes"]["total"], 0,
        )
        self.enviar(
            self.proprietario, "avaliacoes:avaliar", {"nota": 4},
            args=[reserva.pk],
        )
        self.assertEqual(
            self.client.get(anuncio).context["avaliacoes"]["media"], 5,
        )
        self.assertEqual(Avaliacao.objects.count(), 2)
        self.assertContains(self.locatario.get(detalhe), "4/5")
        self.assertContains(self.proprietario.get(detalhe), "5/5")

        for usuario in (self.terceiro, self.staff, self.admin):
            externo = Client()
            externo.force_login(usuario)
            for rota in (
                "reservas:detalhe", "pagamentos:pagar", "locacoes:check_in",
                "locacoes:check_out", "avaliacoes:avaliar",
            ):
                self.assertEqual(externo.get(
                    reverse(rota, args=[reserva.pk]),
                ).status_code, 404)
        documento = reverse("contas:documento_identidade", args=[dono.pk])
        self.assertEqual(funcionario.get(documento).status_code, 404)
        response = self.administrador.get(documento)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content))

    def test_paineis_privados_nao_permanecem_em_cache(self):
        for usuario, rota in (
            (self.terceiro, "contas:painel"),
            (self.staff, "administracao:painel"),
            (self.admin, "administracao:painel"),
        ):
            self.client.force_login(usuario)
            response = self.client.get(reverse(rota))
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("private", response["Cache-Control"])
