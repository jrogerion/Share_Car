from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Usuario
from apps.veiculos.disponibilidade import motivo_indisponibilidade
from apps.veiculos.models import PeriodoAgenda, Veiculo

from .models import Reserva
from .services import (
    AgendaInvalida, ReservaInvalida, adicionar_periodo_agenda, criar_reserva,
)


class AgendaDisponibilidadeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dono = Usuario.objects.create_user(
            "dono-agenda", "dono@example.com", proprietario=True,
        )
        cls.outro = Usuario.objects.create_user("outro", "outro@example.com")
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.dono, caracteristicas="Carro de teste da agenda",
            cidade="Maria da Fé", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="100.00",
            aprovacao="aprovado",
        )

    def setUp(self):
        self.client.force_login(self.dono)
        self.url = reverse("reservas:agenda", args=[self.veiculo.pk])
        self.inicio = timezone.localdate() + timedelta(days=5)
        self.fim = self.inicio + timedelta(days=3)

    def adicionar(self, inicio=None, fim=None, tipo="disponivel", **extras):
        return self.client.post(self.url, {
            "inicio": (inicio or self.inicio).isoformat(),
            "fim": (fim or self.fim).isoformat(), "tipo": tipo, **extras,
        })

    def periodo(self, inicio=None, fim=None, tipo="disponivel"):
        return PeriodoAgenda.objects.create(
            veiculo=self.veiculo, inicio=inicio or self.inicio,
            fim=fim or self.fim, tipo=tipo,
        )

    def reserva(self, status="aceita"):
        return Reserva.objects.create(
            veiculo=self.veiculo, locatario=self.outro,
            inicio=self.inicio, fim=self.fim, status=status,
            preco_diaria="100.00", valor_diarias="300.00", taxas="0.00",
            total="300.00", percentual_comissao="15.00",
        )

    def remover(self, periodo):
        return self.client.post(reverse(
            "reservas:remover_periodo", args=[periodo.pk],
        ))

    def ids_da_busca(self, inicio, fim, rota="veiculos_api:lista"):
        response = self.client.get(reverse(rota), {
            "cidade": "Maria da Fe", "retirada": inicio.isoformat(),
            "devolucao": fim.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        if rota == "veiculos_api:lista":
            return {item["id"] for item in response.json()["results"]}
        return {veiculo.pk for veiculo in response.context["veiculos"]}

    def test_meus_veiculos_oferece_agenda(self):
        response = self.client.get(reverse("veiculos:meus"))
        self.assertContains(response, f'href="{self.url}"')
        response = self.client.get(self.url)
        self.assertContains(response, reverse("veiculos:meus"))
        self.assertIn("no-store", response["Cache-Control"])

    def test_nao_cadastra_inicio_no_passado_ou_intervalo_vazio(self):
        ontem = timezone.localdate() - timedelta(days=1)
        for inicio, fim in ((ontem, self.fim), (self.inicio, self.inicio),
                            (self.fim, self.inicio)):
            response = self.adicionar(inicio, fim)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(PeriodoAgenda.objects.exists())

    def test_hoje_pode_ser_inicio(self):
        self.assertRedirects(
            self.adicionar(timezone.localdate(), self.fim), self.url,
        )

    def test_periodo_repetido_nao_duplica(self):
        self.periodo()
        response = self.adicionar()
        self.assertContains(response, "Este período já está cadastrado")
        self.assertEqual(PeriodoAgenda.objects.count(), 1)

    def test_bloqueio_prevalece_sobre_janela_disponivel(self):
        self.periodo(
            self.inicio - timedelta(days=1), self.fim + timedelta(days=1),
        )
        self.assertRedirects(self.adicionar(tipo="bloqueado"), self.url)
        for rota in ("core:resultados", "veiculos_api:lista"):
            self.assertNotIn(
                self.veiculo.pk, self.ids_da_busca(self.inicio, self.fim, rota),
            )

    def test_bloqueio_nao_pode_sobrepor_reservas_vigentes(self):
        for status in ("solicitada", "aceita", "em_andamento", "concluida"):
            with self.subTest(status=status):
                reserva = self.reserva(status)
                response = self.adicionar(tipo="bloqueado")
                self.assertContains(response, "reserva vigente")
                self.assertFalse(PeriodoAgenda.objects.exists())
                # Somente fixtures no banco de teste isolado.
                reserva.status = "cancelada"
                reserva.save(update_fields=["status"])

    def test_canceladas_e_recusadas_nao_impedem_bloqueio(self):
        self.reserva("cancelada")
        self.reserva("recusada")
        self.assertRedirects(self.adicionar(tipo="bloqueado"), self.url)

    def test_bloqueios_adjacentes_a_reserva_sao_permitidos(self):
        self.reserva()
        self.assertRedirects(self.adicionar(
            self.inicio - timedelta(days=1), self.inicio, "bloqueado",
        ), self.url)
        self.assertRedirects(self.adicionar(
            self.fim, self.fim + timedelta(days=1), "bloqueado",
        ), self.url)

    def test_primeira_disponibilidade_nao_exclui_reservas_existentes(self):
        self.reserva()
        response = self.adicionar(self.fim, self.fim + timedelta(days=2))
        self.assertContains(response, "fora da agenda")
        self.assertFalse(PeriodoAgenda.objects.exists())
        self.assertRedirects(self.adicionar(
            self.inicio - timedelta(days=1), self.fim + timedelta(days=1),
        ), self.url)
        # A janela não libera as datas que continuam reservadas.
        self.assertNotIn(
            self.veiculo.pk, self.ids_da_busca(self.inicio, self.fim),
        )

    def test_remocao_nao_deixa_reserva_fora_das_janelas_restantes(self):
        reserva = self.reserva()
        cobertura = self.periodo()
        self.periodo(self.fim, self.fim + timedelta(days=2))
        response = self.remover(cobertura)
        self.assertRedirects(response, self.url)
        self.assertTrue(PeriodoAgenda.objects.filter(pk=cobertura.pk).exists())
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, "aceita")
        # Uma janela alternativa que cubra a reserva permite a remoção.
        self.periodo(
            self.inicio - timedelta(days=1), self.fim + timedelta(days=1),
        )
        self.remover(cobertura)
        self.assertFalse(PeriodoAgenda.objects.filter(pk=cobertura.pk).exists())

    def test_remover_ultima_janela_preserva_reserva_e_disponibilidade_padrao(self):
        reserva = self.reserva()
        cobertura = self.periodo()
        self.remover(cobertura)
        self.assertFalse(PeriodoAgenda.objects.exists())
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())
        self.assertNotIn(self.veiculo.pk, self.ids_da_busca(self.inicio, self.fim))
        self.assertIn(self.veiculo.pk, self.ids_da_busca(
            self.fim, self.fim + timedelta(days=2),
        ))

    def test_periodo_precisa_caber_inteiro_em_uma_janela(self):
        self.periodo()
        for rota in ("core:resultados", "veiculos_api:lista"):
            self.assertIn(
                self.veiculo.pk, self.ids_da_busca(self.inicio, self.fim, rota),
            )
            self.assertNotIn(self.veiculo.pk, self.ids_da_busca(
                self.inicio - timedelta(days=1), self.fim, rota,
            ))
        motivo = motivo_indisponibilidade(
            self.veiculo, self.inicio - timedelta(days=1), self.fim,
        )
        self.assertIn("fora da disponibilidade", motivo)

    def test_periodos_adjacentes_nao_sao_unidos_implicitamente(self):
        self.periodo()
        self.periodo(self.fim, self.fim + timedelta(days=2))
        self.assertNotIn(self.veiculo.pk, self.ids_da_busca(
            self.inicio, self.fim + timedelta(days=2),
        ))

    def test_outro_usuario_nao_cadastra_nem_remove_periodo(self):
        periodo = self.periodo()
        self.client.force_login(self.outro)
        self.assertEqual(self.adicionar(tipo="bloqueado").status_code, 404)
        self.assertEqual(self.remover(periodo).status_code, 404)
        self.assertEqual(PeriodoAgenda.objects.count(), 1)

    def test_veiculo_forjado_no_post_e_ignorado(self):
        self.adicionar(veiculo=999999, veiculo_id=999999)
        self.assertEqual(PeriodoAgenda.objects.get().veiculo_id, self.veiculo.pk)

    def test_agenda_exibe_reservas_ocupantes_sem_outros_veiculos(self):
        reserva = self.reserva()
        response = self.client.get(self.url)
        self.assertContains(response, reverse("reservas:detalhe", args=[reserva.pk]))
        self.assertEqual(list(response.context["reservas_vigentes"]), [reserva])

    def test_paginacao_da_agenda(self):
        for indice in range(21):
            inicio = self.inicio + timedelta(days=indice * 2)
            self.periodo(inicio, inicio + timedelta(days=1))
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["periodos"]), 20)
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(response.context["periodos"]), 1)

    def test_get_nao_remove_periodos_e_post_exige_csrf(self):
        periodo = self.periodo()
        remover_url = reverse("reservas:remover_periodo", args=[periodo.pk])
        self.assertEqual(self.client.get(remover_url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.dono)
        self.assertEqual(client.post(remover_url).status_code, 403)
        self.assertEqual(client.post(self.url, {}).status_code, 403)
        self.assertTrue(PeriodoAgenda.objects.filter(pk=periodo.pk).exists())


class ConcorrenciaAgendaTests(TransactionTestCase):
    def test_bloqueio_e_reserva_simultaneos_nao_ocupam_mesmas_datas(self):
        dono = Usuario.objects.create_user("dono-concorrencia")
        locatario = Usuario.objects.create_user(
            "locatario-concorrencia", locatario=True,
            aprovacao_cnh="aprovado", cnh_numero="CNH-TESTE-001",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        veiculo = Veiculo.objects.create(
            proprietario=dono, caracteristicas="Veículo de concorrência",
            cidade="Cidade teste", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="100.00",
            aprovacao="aprovado",
        )
        inicio = timezone.localdate() + timedelta(days=5)
        fim = inicio + timedelta(days=3)
        barreira = Barrier(2)

        def executar(acao):
            close_old_connections()
            try:
                barreira.wait(timeout=10)
                if acao == "reserva":
                    criar_reserva(
                        veiculo=veiculo, locatario=locatario,
                        inicio=inicio, fim=fim,
                    )
                else:
                    adicionar_periodo_agenda(
                        veiculo=veiculo, inicio=inicio, fim=fim, tipo="bloqueado",
                    )
                return True
            except (AgendaInvalida, ReservaInvalida):
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(executar, ("reserva", "bloqueio")))
        self.assertEqual(sum(resultados), 1)
        self.assertEqual(
            Reserva.objects.filter(veiculo=veiculo).count()
            + PeriodoAgenda.objects.filter(veiculo=veiculo).count(), 1,
        )
