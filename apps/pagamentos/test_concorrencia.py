from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.contas.models import Usuario
from apps.reservas.models import Reserva
from apps.reservas.services import cancelar_reserva
from apps.veiculos.models import Veiculo

from .models import Pagamento
from .services import PagamentoInvalido, simular_pagamento


class ConcorrenciaPagamentoTests(TransactionTestCase):
    def setUp(self):
        dono = Usuario.objects.create_user("dono-pagamento")
        locatario = Usuario.objects.create_user("locatario-pagamento")
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

    def simultaneamente(self, *acoes):
        barreira = Barrier(len(acoes))

        def executar(acao):
            close_old_connections()
            try:
                # Uma regressão de bloqueio deve falhar, não travar a suíte.
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET statement_timeout = '10s'")
                barreira.wait(timeout=10)
                return acao()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(acoes)) as executor:
            return list(executor.map(executar, acoes))

    def pagar(self):
        try:
            simular_pagamento(
                reserva=self.reserva, meio="pix", resultado="aprovado",
            )
        except PagamentoInvalido:
            return False
        return True

    def test_duas_aprovacoes_simultaneas_criam_um_pagamento(self):
        resultados = self.simultaneamente(self.pagar, self.pagar)

        self.assertEqual(sum(resultados), 1)
        self.assertEqual(Pagamento.objects.count(), 1)
        self.assertEqual(
            Pagamento.objects.get().status, Pagamento.Status.APROVADO,
        )

    def test_pagamento_e_cancelamento_nao_deixam_aprovacao_ativa(self):
        resultados = self.simultaneamente(
            self.pagar, lambda: cancelar_reserva(self.reserva),
        )

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.status, Reserva.Status.CANCELADA)
        self.assertFalse(Pagamento.objects.filter(status="aprovado").exists())
        if resultados[0]:
            self.assertEqual(
                Pagamento.objects.get().status, Pagamento.Status.ESTORNADO,
            )
        else:
            self.assertFalse(Pagamento.objects.exists())
