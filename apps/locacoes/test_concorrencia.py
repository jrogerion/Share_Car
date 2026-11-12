from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from unittest.mock import patch

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone
from PIL import Image

from apps.contas.models import Usuario
from apps.pagamentos.models import Pagamento
from apps.pagamentos.services import simular_pagamento
from apps.reservas.models import Reserva
from apps.reservas.services import ReservaInvalida, cancelar_reserva
from apps.veiculos.models import Veiculo

from .models import FotoRegistroLocacao, RegistroLocacao
from .services import LocacaoInvalida, registrar_locacao


class ConcorrenciaLocacaoTests(TransactionTestCase):
    def setUp(self):
        storage_patch = patch.object(
            FotoRegistroLocacao._meta.get_field("foto"),
            "storage", InMemoryStorage(),
        )
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        dono = Usuario.objects.create_user("dono-vistoria")
        locatario = Usuario.objects.create_user("locatario-vistoria")
        veiculo = Veiculo.objects.create(
            proprietario=dono, caracteristicas="Carro de teste",
            cidade="Cidade teste", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="150.00",
            aprovacao=Veiculo.Aprovacao.APROVADO,
        )
        inicio = timezone.localdate() + timedelta(days=5)
        self.reserva = Reserva.objects.create(
            veiculo=veiculo, locatario=locatario, inicio=inicio,
            fim=inicio + timedelta(days=3), status=Reserva.Status.ACEITA,
            preco_diaria="150.00", valor_diarias="450.00", total="450.00",
            percentual_comissao="15.00",
        )
        simular_pagamento(
            reserva=self.reserva, meio="pix", resultado="aprovado",
        )

    def registrar(self, tipo="check_in"):
        buffer = BytesIO()
        Image.new("RGB", (2, 2)).save(buffer, format="PNG")
        try:
            registrar_locacao(
                reserva=self.reserva, tipo=tipo, quilometragem=1000,
                nivel_combustivel=50, fotos=[SimpleUploadedFile(
                    "foto.png", buffer.getvalue(), content_type="image/png",
                )],
            )
        except LocacaoInvalida:
            return False
        return True

    def simultaneamente(self, *acoes):
        barreira = Barrier(len(acoes))

        def executar(acao):
            close_old_connections()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET statement_timeout = '10s'")
                barreira.wait(timeout=10)
                return acao()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(acoes)) as executor:
            return list(executor.map(executar, acoes))

    def test_check_ins_simultaneos_registram_uma_vistoria(self):
        resultados = self.simultaneamente(self.registrar, self.registrar)

        self.assertEqual(sum(resultados), 1)
        self.assertEqual(RegistroLocacao.objects.count(), 1)
        self.assertEqual(FotoRegistroLocacao.objects.count(), 1)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.EM_ANDAMENTO)

    def test_check_outs_simultaneos_concluem_apenas_uma_vez(self):
        self.registrar()
        resultados = self.simultaneamente(
            lambda: self.registrar("check_out"),
            lambda: self.registrar("check_out"),
        )

        self.assertEqual(sum(resultados), 1)
        self.assertEqual(RegistroLocacao.objects.count(), 2)
        self.assertEqual(FotoRegistroLocacao.objects.count(), 2)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.CONCLUIDA)

    def test_cancelamento_e_check_in_nao_podem_ambos_vencer(self):
        def cancelar():
            try:
                cancelar_reserva(self.reserva)
            except ReservaInvalida:
                return False
            return True

        resultados = self.simultaneamente(self.registrar, cancelar)

        self.assertEqual(sum(resultados), 1)
        self.reserva.refresh_from_db()
        pagamento = Pagamento.objects.get(reserva=self.reserva)
        if resultados[0]:
            self.assertEqual(self.reserva.status, Reserva.Status.EM_ANDAMENTO)
            self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
            self.assertEqual(RegistroLocacao.objects.count(), 1)
        else:
            self.assertEqual(self.reserva.status, Reserva.Status.CANCELADA)
            self.assertEqual(pagamento.status, Pagamento.Status.ESTORNADO)
            self.assertFalse(RegistroLocacao.objects.exists())
