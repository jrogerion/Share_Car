from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CondicoesMigrationTests(TransactionTestCase):
    def test_migration_preserva_pagamento_pix_antigo(self):
        anterior = [("pagamentos", "0001_initial")]
        destino = [("pagamentos", "0002_condicoes_simulacao")]
        executor = MigrationExecutor(connection)
        executor.migrate(anterior)
        try:
            apps = executor.loader.project_state(anterior).apps
            usuario = apps.get_model("contas", "Usuario").objects.create(username="migration-dono")
            locatario = apps.get_model("contas", "Usuario").objects.create(username="migration-locatario")
            veiculo = apps.get_model("veiculos", "Veiculo").objects.create(
                proprietario=usuario, caracteristicas="Teste de preservação",
                cidade="Campinas", categoria="Hatch", cambio="Manual",
                combustivel="Flex", passageiros=5, preco_diaria="150.00",
            )
            reserva = apps.get_model("reservas", "Reserva").objects.create(
                veiculo=veiculo, locatario=locatario, inicio="2026-01-01",
                fim="2026-01-04", status="aceita", preco_diaria="150.00",
                valor_diarias="450.00", taxas="0.00", total="450.00",
                percentual_comissao="15.00",
            )
            pagamento = apps.get_model("pagamentos", "Pagamento").objects.create(
                reserva=reserva, meio="pix", status="aprovado",
                valor_bruto="450.00", comissao="67.50", repasse_proprietario="382.50",
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(destino)
        apps = executor.loader.project_state(destino).apps
        atualizado = apps.get_model("pagamentos", "Pagamento").objects.get(pk=pagamento.pk)
        self.assertEqual(atualizado.valor_bruto, Decimal("450.00"))
        self.assertEqual(atualizado.comissao, Decimal("67.50"))
        self.assertEqual(atualizado.repasse_proprietario, Decimal("382.50"))
        self.assertEqual(atualizado.parcelas, 1)
        self.assertEqual(atualizado.juros, 0)
        self.assertEqual(atualizado.desconto, 0)
        self.assertEqual(atualizado.status, "aprovado")
