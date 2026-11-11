from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.administracao.models import ConfiguracaoComissao
from apps.contas.models import Usuario
from apps.veiculos.models import PeriodoAgenda, Veiculo

from .models import Reserva
from .services import (
    ReservaInvalida, aceitar_reserva, cancelar_reserva, criar_reserva,
    recusar_reserva,
)


class FluxoReservaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dono = Usuario.objects.create_user("dono", "dono@example.com")
        cls.locatario = Usuario.objects.create_user(
            "locatario", "locatario@example.com", locatario=True,
            cnh_numero="CNH-TESTE-001", aprovacao_cnh="aprovado",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.outro = Usuario.objects.create_user("outro", "outro@example.com")
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.dono, caracteristicas="Veículo fictício",
            cidade="Campinas", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="150.00",
            aprovacao="aprovado",
        )

    def setUp(self):
        self.inicio = timezone.localdate() + timedelta(days=5)
        self.fim = self.inicio + timedelta(days=3)
        self.client.force_login(self.locatario)
        self.url = reverse("reservas:criar", args=[self.veiculo.pk])
        self.dados = {
            "retirada": self.inicio.isoformat(), "devolucao": self.fim.isoformat(),
        }

    def solicitar(self):
        return criar_reserva(
            veiculo=self.veiculo, locatario=self.locatario,
            inicio=self.inicio, fim=self.fim,
        )

    def test_exige_elegibilidade_atualizada_mesmo_com_usuario_em_cache(self):
        base = {
            "is_active": True, "locatario": True, "cnh_numero": "CNH-TESTE",
            "aprovacao_cnh": "aprovado", "cnh_validade": self.fim,
        }
        for alteracoes in (
            {"is_active": False}, {"locatario": False}, {"cnh_numero": ""},
            {"cnh_validade": None}, {"aprovacao_cnh": "pendente"},
            {"aprovacao_cnh": "rejeitado"},
            {"cnh_validade": timezone.localdate() - timedelta(days=1)},
            {"cnh_validade": self.fim - timedelta(days=1)},
        ):
            with self.subTest(alteracoes=alteracoes):
                Usuario.objects.filter(pk=self.locatario.pk).update(
                    **{**base, **alteracoes},
                )
                with self.assertRaises(ReservaInvalida):
                    self.solicitar()
                self.assertFalse(Reserva.objects.exists())

    def test_post_forjado_nao_escolhe_locatario_status_ou_valores(self):
        Usuario.objects.filter(pk=self.locatario.pk).update(cnh_validade=self.fim)
        response = self.client.post(self.url, {
            **self.dados, "locatario": self.outro.pk, "status": "aceita",
            "preco_diaria": "0.01", "total": "0.01", "percentual_comissao": "0",
        })
        reserva = Reserva.objects.get()
        self.assertRedirects(response, reverse("reservas:detalhe", args=[reserva.pk]))
        self.assertEqual(reserva.locatario_id, self.locatario.pk)
        self.assertEqual(reserva.status, "solicitada")
        self.assertEqual(reserva.preco_diaria, Decimal("150.00"))
        self.assertEqual(reserva.total, Decimal("450.00"))

    def test_detalhes_orientam_completar_perfil_sem_botao_de_solicitacao(self):
        Usuario.objects.filter(pk=self.locatario.pk).update(aprovacao_cnh="pendente")
        url = reverse("core:detalhes", args=[self.veiculo.pk])
        response = self.client.get(url, self.dados)
        self.assertContains(response, "CNH do locatário precisa estar aprovada")
        self.assertContains(response, reverse("contas:perfil"))
        self.assertNotContains(response, f'action="{self.url}"')
        response = self.client.post(self.url, self.dados)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Reserva.objects.exists())

    def test_servico_revalida_publicacao_apos_leitura_do_anuncio(self):
        for alteracoes in (
            {"ativo": False}, {"bloqueado": True}, {"aprovacao": "pendente"},
        ):
            with self.subTest(alteracoes=alteracoes):
                Veiculo.objects.filter(pk=self.veiculo.pk).update(**{
                    "ativo": True, "bloqueado": False, "aprovacao": "aprovado",
                    **alteracoes,
                })
                with self.assertRaisesMessage(ReservaInvalida, "novas reservas"):
                    self.solicitar()
                self.assertFalse(Reserva.objects.exists())

    def test_aceite_revalida_cnh_e_nao_altera_valores(self):
        reserva = self.solicitar()
        Usuario.objects.filter(pk=self.locatario.pk).update(aprovacao_cnh="rejeitado")
        with self.assertRaisesMessage(ReservaInvalida, "CNH"):
            aceitar_reserva(reserva)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "solicitada")
        Usuario.objects.filter(pk=self.locatario.pk).update(aprovacao_cnh="aprovado")
        Veiculo.objects.filter(pk=self.veiculo.pk).update(preco_diaria="999.00")
        ConfiguracaoComissao.objects.update_or_create(
            pk=1, defaults={"percentual": "25.00"},
        )
        aceitar_reserva(reserva)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "aceita")
        self.assertEqual(reserva.total, Decimal("450.00"))
        self.assertEqual(reserva.preco_diaria, Decimal("150.00"))
        self.assertEqual(reserva.percentual_comissao, Decimal("15.00"))

    def test_aceite_revalida_anuncio_e_janela_da_agenda(self):
        reserva = self.solicitar()
        Veiculo.objects.filter(pk=self.veiculo.pk).update(bloqueado=True)
        with self.assertRaisesMessage(ReservaInvalida, "publicado"):
            aceitar_reserva(reserva)
        Veiculo.objects.filter(pk=self.veiculo.pk).update(bloqueado=False)
        PeriodoAgenda.objects.create(
            veiculo=self.veiculo, inicio=self.fim,
            fim=self.fim + timedelta(days=2), tipo="disponivel",
        )
        with self.assertRaisesMessage(ReservaInvalida, "disponibilidade"):
            aceitar_reserva(reserva)

    def test_aceite_bloqueado_oferece_recusa_ao_proprietario(self):
        reserva = self.solicitar()
        Usuario.objects.filter(pk=self.locatario.pk).update(aprovacao_cnh="pendente")
        self.client.force_login(self.dono)
        response = self.client.get(reverse("reservas:detalhe", args=[reserva.pk]))
        self.assertFalse(response.context["pode_aceitar"])
        self.assertTrue(response.context["pode_recusar"])
        self.assertContains(response, "CNH do locatário precisa estar aprovada")
        response = self.client.post(reverse("reservas:aceitar", args=[reserva.pk]))
        self.assertEqual(response.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "solicitada")

    def test_solicitacao_com_inicio_passado_nao_pode_ser_aceita(self):
        reserva = self.solicitar()
        Reserva.objects.filter(pk=reserva.pk).update(
            inicio=timezone.localdate() - timedelta(days=1),
        )
        with self.assertRaisesMessage(ReservaInvalida, "passado"):
            aceitar_reserva(reserva)

    def test_recusa_e_cancelamento_liberam_datas_sem_apagar_historico(self):
        reserva = self.solicitar()
        recusar_reserva(reserva)
        segunda = self.solicitar()
        aceitar_reserva(segunda)
        cancelar_reserva(segunda)
        terceira = self.solicitar()
        self.assertEqual(terceira.status, "solicitada")
        self.assertEqual(Reserva.objects.count(), 3)

    def test_transicoes_invalidas_nao_reabrem_reserva(self):
        reserva = self.solicitar()
        for status in ("recusada", "cancelada", "em_andamento", "concluida"):
            with self.subTest(status=status):
                Reserva.objects.filter(pk=reserva.pk).update(status=status)
                for acao in (aceitar_reserva, recusar_reserva, cancelar_reserva):
                    with self.assertRaises(ReservaInvalida):
                        acao(reserva)
                reserva.refresh_from_db()
                self.assertEqual(reserva.status, status)

    def test_datas_elegiveis_mas_total_excessivo_nao_geram_erro_500(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(preco_diaria="99999999.99")
        fim = self.inicio + timedelta(days=200)
        dados = {**self.dados, "devolucao": fim.isoformat()}
        response = self.client.get(
            reverse("core:detalhes", args=[self.veiculo.pk]), dados,
        )
        self.assertContains(response, "total excede o limite")
        response = self.client.post(self.url, dados)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Reserva.objects.exists())

    def test_acoes_nao_permitidas_a_terceiros_e_exigem_csrf(self):
        reserva = self.solicitar()
        self.client.force_login(self.outro)
        for acao in ("aceitar", "recusar", "cancelar"):
            url = reverse(f"reservas:{acao}", args=[reserva.pk])
            self.assertEqual(self.client.post(url).status_code, 404)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.dono)
        for acao in ("aceitar", "recusar"):
            self.assertEqual(client.post(reverse(
                f"reservas:{acao}", args=[reserva.pk],
            )).status_code, 403)
        client.force_login(self.locatario)
        self.assertEqual(client.post(self.url, self.dados).status_code, 403)
        self.assertEqual(client.post(reverse(
            "reservas:cancelar", args=[reserva.pk],
        )).status_code, 403)

    def test_minhas_reservas_paginadas_e_isoladas(self):
        for indice in range(11):
            inicio = self.inicio + timedelta(days=indice * 4)
            criar_reserva(
                veiculo=self.veiculo, locatario=self.locatario,
                inicio=inicio, fim=inicio + timedelta(days=3),
            )
        response = self.client.get(reverse("reservas:minhas"))
        self.assertEqual(response.context["pagina_locatario"].paginator.count, 11)
        self.assertEqual(len(response.context["como_locatario"]), 10)
        self.assertContains(response, "locatario_page=2")
        self.assertIn("no-store", response["Cache-Control"])
        response = self.client.get(reverse("reservas:minhas"), {"locatario_page": 2})
        self.assertEqual(len(response.context["como_locatario"]), 1)
        self.client.force_login(self.dono)
        response = self.client.get(reverse("reservas:minhas"))
        self.assertEqual(response.context["pagina_proprietario"].paginator.count, 11)
        self.client.force_login(self.outro)
        response = self.client.get(reverse("reservas:minhas"))
        self.assertFalse(response.context["como_locatario"])
        self.assertFalse(response.context["como_proprietario"])


class ConcorrenciaSolicitacaoTests(TransactionTestCase):
    def test_duas_solicitacoes_simultaneas_geram_uma_unica_reserva(self):
        dono = Usuario.objects.create_user("dono-concorrencia")
        locatarios = [Usuario.objects.create_user(
            f"locatario-{indice}", locatario=True, cnh_numero="CNH-TESTE",
            aprovacao_cnh="aprovado",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        ) for indice in range(2)]
        veiculo = Veiculo.objects.create(
            proprietario=dono, caracteristicas="Carro concorrente",
            cidade="Cidade teste", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="100.00",
            aprovacao="aprovado",
        )
        inicio = timezone.localdate() + timedelta(days=5)
        barreira = Barrier(2)

        def solicitar(locatario):
            close_old_connections()
            try:
                barreira.wait(timeout=10)
                criar_reserva(
                    veiculo=veiculo, locatario=locatario,
                    inicio=inicio, fim=inicio + timedelta(days=3),
                )
                return True
            except ReservaInvalida:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(solicitar, locatarios))
        self.assertEqual(sum(resultados), 1)
        self.assertEqual(Reserva.objects.count(), 1)
