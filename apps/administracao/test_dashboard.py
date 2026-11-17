from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contas.forms import PerfilUsuarioForm
from apps.contas.models import Usuario
from apps.pagamentos.models import Pagamento
from apps.pagamentos.services import simular_pagamento
from apps.reservas.models import Reserva
from apps.reservas.services import ReservaInvalida, criar_reserva, cancelar_reserva
from apps.veiculos.models import Veiculo

from .dashboard import indicadores_financeiros


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            "admin-dashboard", "admin-dashboard@example.com", is_staff=True,
            first_name="Admin", last_name="Teste", locatario=True, proprietario=True,
        )
        cls.dono = Usuario.objects.create_user("dono-dashboard", "dono@example.com")
        cls.cliente = Usuario.objects.create_user("cliente-dashboard", "cliente@example.com")
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.dono, caracteristicas="Veículo fictício",
            cidade="Campinas", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="450.00",
            aprovacao="aprovado",
        )

    def reserva(self, indice, status="aceita", percentual="15.00", usuario=None):
        inicio = timezone.localdate() + timedelta(days=10 + indice * 5)
        return Reserva.objects.create(
            veiculo=self.veiculo, locatario=usuario or self.cliente,
            inicio=inicio, fim=inicio + timedelta(days=1), status=status,
            preco_diaria="450.00", valor_diarias="450.00", taxas=0,
            total="450.00", percentual_comissao=percentual,
        )

    def test_financeiro_separa_ganhos_previstos_estornos_e_ajustes(self):
        pix = self.reserva(0)
        simular_pagamento(reserva=pix, meio="pix", resultado="aprovado")
        cartao = self.reserva(1, percentual="10.00")
        simular_pagamento(reserva=cartao, meio="cartao", parcelas=8, resultado="aprovado")
        estorno = self.reserva(2)
        simular_pagamento(reserva=estorno, meio="cartao", parcelas=7, resultado="aprovado")
        cancelar_reserva(estorno)
        self.reserva(3)
        recusado = self.reserva(4)
        simular_pagamento(reserva=recusado, meio="pix", resultado="recusado")
        self.reserva(5, status="solicitada")
        dados = indicadores_financeiros(Reserva.objects.all())
        self.assertEqual(dados["financeiro"], {
            "comissao": Decimal("112.50"), "prevista": Decimal("135.00"),
            "total_aprovado": Decimal("913.50"), "estornos": Decimal("481.50"),
            "juros": Decimal("36.00"), "descontos": Decimal("22.50"),
            "repasses": Decimal("787.50"),
        })
        self.assertEqual(sum(item["total"] for item in dados["grafico_status"]), 6)
        self.assertEqual([item["total"] for item in dados["grafico_meios"]], [1, 1])

    def test_dashboard_vazio_e_periodos_invalidos(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("administracao:painel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["financeiro"]["comissao"], 0)
        self.assertContains(response, "sem receita ou cobrança real")
        for filtros in ({"inicio": "inválida"}, {"inicio": "2027-01-02", "fim": "2027-01-01"}):
            response = self.client.get(reverse("administracao:painel"), filtros)
            self.assertContains(response, "Corrija o período")
            self.assertNotContains(response, 'aria-label="Indicadores financeiros simulados"')

    def test_filtro_inclusivo_usa_retirada_e_snapshot_da_comissao(self):
        primeira = self.reserva(0)
        self.reserva(1)
        simular_pagamento(reserva=primeira, meio="pix", resultado="aprovado")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("administracao:painel"), {
            "inicio": primeira.inicio.isoformat(), "fim": primeira.inicio.isoformat(),
        })
        self.assertEqual(response.context["financeiro"]["comissao"], Decimal("67.50"))
        self.assertEqual(response.context["financeiro"]["prevista"], 0)
        self.assertEqual(response.context["total_reservas_dashboard"], 1)

    def test_conta_administrativa_nao_pode_operar_fluxos_pessoais(self):
        reserva = self.reserva(0, usuario=self.admin)
        self.client.force_login(self.admin)
        rotas = [
            ("core:veiculo", []), ("veiculos:meus", []),
            ("veiculos:editar", [self.veiculo.pk]), ("veiculos:fotos", [self.veiculo.pk]),
            ("reservas:minhas", []), ("reservas:criar", [self.veiculo.pk]),
            ("reservas:aceitar", [reserva.pk]), ("reservas:cancelar", [reserva.pk]),
            ("reservas:recusar", [reserva.pk]), ("reservas:agenda", [self.veiculo.pk]),
            ("reservas:remover_periodo", [1]), ("reservas:detalhe", [reserva.pk]),
            ("pagamentos:pagar", [reserva.pk]), ("locacoes:check_in", [reserva.pk]),
            ("locacoes:check_out", [reserva.pk]), ("avaliacoes:avaliar", [reserva.pk]),
        ]
        for nome, args in rotas:
            for metodo in (self.client.get, self.client.post):
                with self.subTest(rota=nome, metodo=metodo.__name__):
                    response = metodo(reverse(nome, args=args))
                    self.assertRedirects(response, reverse("administracao:painel"), fetch_redirect_response=False)
        self.assertEqual(Reserva.objects.count(), 1)
        self.assertFalse(Pagamento.objects.exists())
        self.assertEqual(Veiculo.objects.count(), 1)
        self.assertEqual(Reserva.objects.get().status, "aceita")
        with self.assertRaises(ReservaInvalida):
            criar_reserva(
                veiculo=self.veiculo, locatario=self.admin,
                inicio=reserva.inicio + timedelta(days=5),
                fim=reserva.fim + timedelta(days=5),
            )

    def test_menu_e_perfil_administrativos_preservam_registros(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, 'href="' + reverse("reservas:minhas") + '"')
        self.assertNotContains(response, 'href="' + reverse("core:veiculo") + '"')
        self.assertContains(response, reverse("administracao:painel"))
        form = PerfilUsuarioForm({
            "first_name": "Novo", "last_name": "Nome", "locatario": "", "proprietario": "",
        }, instance=self.admin)
        self.assertEqual(set(form.fields), {"first_name", "last_name"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.proprietario)
        self.assertTrue(self.admin.locatario)
        self.assertTrue(self.admin.is_staff)

    def test_consulta_administrativa_somente_leitura_e_restrita(self):
        reserva = self.reserva(0)
        url = reverse("administracao:reserva", args=[reserva.pk])
        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertContains(response, "Consulta somente leitura")
        self.assertNotContains(response, "Simular pagamento")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(url).status_code, 405)
        self.client.force_login(self.cliente)
        self.assertRedirects(self.client.get(url), reverse("contas:painel"))
