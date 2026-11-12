from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.contas.models import Usuario
from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .models import Avaliacao
from .services import (
    AvaliacaoInvalida, avaliar_reserva, resumo_avaliacoes_veiculo,
)


class ConcorrenciaAvaliacaoTests(TransactionTestCase):
    def setUp(self):
        self.dono = Usuario.objects.create_user("dono-avaliacao")
        self.locatario = Usuario.objects.create_user("locatario-avaliacao")
        self.veiculo = Veiculo.objects.create(
            proprietario=self.dono, caracteristicas="Carro de teste",
            cidade="Cidade teste", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="150.00",
            aprovacao=Veiculo.Aprovacao.APROVADO,
        )
        inicio = timezone.localdate() + timedelta(days=5)
        self.reserva = Reserva.objects.create(
            veiculo=self.veiculo, locatario=self.locatario, inicio=inicio,
            fim=inicio + timedelta(days=3), status=Reserva.Status.CONCLUIDA,
            preco_diaria="150.00", valor_diarias="450.00", total="450.00",
            percentual_comissao="15.00",
        )

    def avaliar_simultaneamente(self, autores):
        barreira = Barrier(len(autores))

        def avaliar(autor):
            close_old_connections()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET statement_timeout = '10s'")
                barreira.wait(timeout=10)
                avaliar_reserva(reserva=self.reserva, autor=autor, nota=5)
                return True
            except AvaliacaoInvalida:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(autores)) as executor:
            return list(executor.map(avaliar, autores))

    def test_mesmo_autor_nao_consegue_enviar_duas_vezes(self):
        resultados = self.avaliar_simultaneamente([
            self.locatario, self.locatario,
        ])

        self.assertEqual(sum(resultados), 1)
        self.assertEqual(Avaliacao.objects.count(), 1)
        self.assertEqual(resumo_avaliacoes_veiculo(self.veiculo)["total"], 0)

    def test_ambas_as_partes_podem_avaliar_simultaneamente(self):
        resultados = self.avaliar_simultaneamente([self.locatario, self.dono])

        self.assertEqual(sum(resultados), 2)
        self.assertEqual(Avaliacao.objects.count(), 2)
        self.assertEqual(
            resumo_avaliacoes_veiculo(self.veiculo), {"media": 5.0, "total": 1},
        )
