import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.contas.models import Usuario
from apps.pagamentos.models import Pagamento
from apps.pagamentos.services import simular_pagamento
from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .forms import RegistroLocacaoForm
from .models import FotoRegistroLocacao, RegistroLocacao
from .services import LocacaoInvalida, registrar_locacao


class LocacaoBaseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = tempfile.mkdtemp()
        cls.patch_storage = patch.object(
            FotoRegistroLocacao._meta.get_field("foto"),
            "storage",
            FileSystemStorage(location=cls.media_dir),
        )
        cls.patch_storage.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch_storage.stop()
        shutil.rmtree(cls.media_dir, ignore_errors=True)
        super().tearDownClass()

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

    def criar_reserva(self, *, status=Reserva.Status.ACEITA):
        inicio = timezone.localdate() + timedelta(days=5)
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

    def aprovar_pagamento(self, reserva):
        return simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="aprovado",
        )

    @staticmethod
    def fotos(quantidade=1):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), "white").save(buffer, format="JPEG")
        return [
            SimpleUploadedFile(
                f"foto-{indice}.jpg",
                buffer.getvalue(),
                content_type="image/jpeg",
            )
            for indice in range(quantidade)
        ]

    def registrar(self, reserva, tipo, **dados):
        padrao = {
            "reserva": reserva,
            "tipo": tipo,
            "quilometragem": 10000,
            "nivel_combustivel": 80,
            "fotos": self.fotos(),
        }
        padrao.update(dados)
        return registrar_locacao(**padrao)


class RegistroLocacaoServiceTests(LocacaoBaseTests):
    def test_servico_rejeita_numeros_invalidos_sem_alterar_reserva(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        for dados in (
            {"quilometragem": -1}, {"quilometragem": 2_147_483_648},
            {"quilometragem": 1.5}, {"nivel_combustivel": -1},
            {"nivel_combustivel": 101}, {"nivel_combustivel": True},
        ):
            with self.subTest(dados=dados):
                with self.assertRaises(LocacaoInvalida):
                    self.registrar(reserva, "check_in", **dados)
                self.assertFalse(RegistroLocacao.objects.exists())
                self.assertFalse(FotoRegistroLocacao.objects.exists())
                reserva.refresh_from_db()
                self.assertEqual(reserva.status, Reserva.Status.ACEITA)

    def test_servico_rejeita_imagens_invalidas_e_quantidade(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        for fotos in (
            [], self.fotos(7),
            [SimpleUploadedFile("falsa.jpg", b"nao-e-imagem", "image/jpeg")],
        ):
            with self.subTest(quantidade=len(fotos)):
                with self.assertRaises(LocacaoInvalida):
                    self.registrar(reserva, "check_in", fotos=fotos)
                self.assertFalse(RegistroLocacao.objects.exists())

    def test_check_out_duplicado_nao_altera_registro_anterior(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.registrar(reserva, "check_in")
        self.registrar(reserva, "check_out", quilometragem=10100)

        with self.assertRaises(LocacaoInvalida):
            self.registrar(reserva, "check_out", quilometragem=10200)
        self.assertEqual(RegistroLocacao.objects.count(), 2)
        self.assertEqual(
            RegistroLocacao.objects.get(tipo="check_out").quilometragem, 10100,
        )

    def test_falha_ao_gravar_foto_nao_avanca_status(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        with patch.object(
            FotoRegistroLocacao.objects, "create", side_effect=OSError,
        ):
            with self.assertRaises(OSError):
                self.registrar(reserva, "check_in")
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.ACEITA)
        self.assertFalse(RegistroLocacao.objects.exists())

    def test_check_in_exige_pagamento_aprovado(self):
        reserva = self.criar_reserva()

        with self.assertRaises(LocacaoInvalida):
            self.registrar(reserva, RegistroLocacao.Tipo.CHECK_IN)

    def test_check_in_com_pagamento_recusado_e_bloqueado(self):
        reserva = self.criar_reserva()
        simular_pagamento(
            reserva=reserva,
            meio=Pagamento.Meio.PIX,
            resultado="recusado",
        )

        with self.assertRaises(LocacaoInvalida):
            self.registrar(reserva, RegistroLocacao.Tipo.CHECK_IN)

    def test_check_in_registra_fotos_e_inicia_locacao(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)

        registro = self.registrar(
            reserva,
            RegistroLocacao.Tipo.CHECK_IN,
            nivel_combustivel=90,
            fotos=self.fotos(2),
        )

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.EM_ANDAMENTO)
        self.assertEqual(registro.quilometragem, 10000)
        self.assertEqual(registro.nivel_combustivel, 90)
        self.assertEqual(registro.fotos.count(), 2)

    def test_check_in_duplicado_e_bloqueado(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.registrar(reserva, RegistroLocacao.Tipo.CHECK_IN)

        with self.assertRaises(LocacaoInvalida):
            self.registrar(reserva, RegistroLocacao.Tipo.CHECK_IN)

    def test_check_out_exige_check_in(self):
        reserva = self.criar_reserva(status=Reserva.Status.EM_ANDAMENTO)

        with self.assertRaises(LocacaoInvalida):
            self.registrar(reserva, RegistroLocacao.Tipo.CHECK_OUT)

    def test_check_out_nao_aceita_quilometragem_menor(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.registrar(
            reserva,
            RegistroLocacao.Tipo.CHECK_IN,
            quilometragem=15000,
        )

        with self.assertRaises(LocacaoInvalida):
            self.registrar(
                reserva,
                RegistroLocacao.Tipo.CHECK_OUT,
                quilometragem=14000,
            )

    def test_check_out_conclui_locacao(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.registrar(
            reserva,
            RegistroLocacao.Tipo.CHECK_IN,
            quilometragem=15000,
        )

        registro = self.registrar(
            reserva,
            RegistroLocacao.Tipo.CHECK_OUT,
            quilometragem=15420,
            nivel_combustivel=70,
            fotos=self.fotos(3),
        )

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CONCLUIDA)
        self.assertEqual(registro.quilometragem, 15420)
        self.assertEqual(registro.fotos.count(), 3)


class RegistroLocacaoFormTests(LocacaoBaseTests):
    def test_formulario_rejeita_conteudo_falso_e_gif_disfarcado(self):
        buffer = BytesIO()
        Image.new("RGB", (2, 2)).save(buffer, format="GIF")
        for conteudo in (b"arquivo-invalido", buffer.getvalue()):
            form = RegistroLocacaoForm(
                data={"quilometragem": 100, "nivel_combustivel": 50},
                files={"fotos": [SimpleUploadedFile(
                    "foto.png", conteudo, content_type="image/png",
                )]},
            )
            self.assertFalse(form.is_valid())
            self.assertIn("fotos", form.errors)

    def test_formulario_rejeita_excesso_de_fotos_e_tamanho(self):
        for fotos in (
            [], self.fotos(7),
            [SimpleUploadedFile("grande.jpg", b"x" * (5 * 1024 * 1024 + 1))],
        ):
            form = RegistroLocacaoForm(
                data={"quilometragem": 100, "nivel_combustivel": 50},
                files={"fotos": fotos},
            )
            self.assertFalse(form.is_valid())
            self.assertIn("fotos", form.errors)

    def test_formulario_limita_resolucao(self):
        with patch("apps.locacoes.validacoes.MAXIMO_PIXELS", 1):
            form = RegistroLocacaoForm(
                data={"quilometragem": 100, "nivel_combustivel": 50},
                files={"fotos": self.fotos()},
            )
            self.assertFalse(form.is_valid())
            self.assertIn("fotos", form.errors)

    def test_limites_numericos_do_formulario(self):
        for dados in (
            {"quilometragem": -1, "nivel_combustivel": 50},
            {"quilometragem": 2_147_483_648, "nivel_combustivel": 50},
            {"quilometragem": 100, "nivel_combustivel": -1},
        ):
            form = RegistroLocacaoForm(data=dados, files={"fotos": self.fotos()})
            self.assertFalse(form.is_valid())

    def test_formulario_aceita_multiplas_fotos_validas(self):
        form = RegistroLocacaoForm(
            data={"quilometragem": "10000", "nivel_combustivel": "80"},
            files={"fotos": self.fotos(2)},
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["fotos"]), 2)

    def test_formulario_recusa_extensao_invalida(self):
        arquivo = SimpleUploadedFile(
            "foto.gif",
            b"conteudo",
            content_type="image/gif",
        )
        form = RegistroLocacaoForm(
            data={"quilometragem": "10000", "nivel_combustivel": "80"},
            files={"fotos": [arquivo]},
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("fotos", form.errors)

    def test_formulario_recusa_combustivel_acima_de_100(self):
        form = RegistroLocacaoForm(
            data={"quilometragem": "10000", "nivel_combustivel": "101"},
            files={"fotos": self.fotos()},
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("nivel_combustivel", form.errors)


class RegistrarLocacaoViewTests(LocacaoBaseTests):
    def test_bloqueia_formulario_e_post_sem_pagamento_ou_check_in(self):
        reserva = self.criar_reserva()
        self.client.force_login(self.locatario)
        for rota in ("locacoes:check_in", "locacoes:check_out"):
            url = reverse(rota, args=[reserva.pk])
            for response in (self.client.get(url), self.client.post(url, {})):
                self.assertRedirects(
                    response, reverse("reservas:detalhe", args=[reserva.pk]),
                )
        self.assertFalse(RegistroLocacao.objects.exists())

    def test_visitante_e_proprietario_nao_registram_vistoria(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        for rota in ("locacoes:check_in", "locacoes:check_out"):
            url = reverse(rota, args=[reserva.pk])
            for usuario in (None, self.proprietario, self.outro):
                self.client.logout()
                if usuario:
                    self.client.force_login(usuario)
                for metodo in (self.client.get, self.client.post):
                    self.assertEqual(metodo(url).status_code, 404 if usuario else 302)
        self.assertFalse(RegistroLocacao.objects.exists())

    def test_formulario_nao_fica_em_cache_e_post_exige_csrf(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.locatario)
        url = reverse("locacoes:check_in", args=[reserva.pk])
        response = client.get(url)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(client.post(url, {}).status_code, 403)
        response = client.post(url, {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "quilometragem": 100, "nivel_combustivel": 50,
            "fotos": self.fotos(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RegistroLocacao.objects.count(), 1)

    def test_devolucao_com_km_menor_mantem_dados_para_correcao(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.registrar(reserva, "check_in", quilometragem=1000)
        self.client.force_login(self.locatario)
        response = self.client.post(
            reverse("locacoes:check_out", args=[reserva.pk]), {
                "quilometragem": 900, "nivel_combustivel": 60,
                "fotos": self.fotos(),
            },
        )
        self.assertContains(response, "não pode ser menor")
        self.assertEqual(response.context["form"]["quilometragem"].value(), "900")
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.EM_ANDAMENTO)

    def test_fluxo_completo_preserva_registros_e_bloqueia_repeticao(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.client.force_login(self.locatario)
        for rota, km, status in (
            ("locacoes:check_in", 1000, Reserva.Status.EM_ANDAMENTO),
            ("locacoes:check_out", 1000, Reserva.Status.CONCLUIDA),
        ):
            url = reverse(rota, args=[reserva.pk])
            response = self.client.post(url, {
                "quilometragem": km, "nivel_combustivel": 0,
                "fotos": self.fotos(),
                "reserva": "99999", "tipo": "invalido", "status": "cancelada",
            })
            self.assertRedirects(
                response, reverse("reservas:detalhe", args=[reserva.pk]),
            )
            reserva.refresh_from_db()
            self.assertEqual(reserva.status, status)
            self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(RegistroLocacao.objects.count(), 2)
        self.assertEqual(FotoRegistroLocacao.objects.count(), 2)

    def test_locatario_registra_check_in_pela_view(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.client.force_login(self.locatario)

        response = self.client.post(
            reverse("locacoes:check_in", args=[reserva.pk]),
            {
                "quilometragem": "10000",
                "nivel_combustivel": "80",
                "fotos": self.fotos(),
            },
        )

        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.EM_ANDAMENTO)

    def test_outro_usuario_nao_registra_vistoria(self):
        reserva = self.criar_reserva()
        self.aprovar_pagamento(reserva)
        self.client.force_login(self.outro)

        response = self.client.get(
            reverse("locacoes:check_in", args=[reserva.pk])
        )

        self.assertEqual(response.status_code, 404)
