import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        return [
            SimpleUploadedFile(
                f"foto-{indice}.jpg",
                b"conteudo-da-foto",
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
