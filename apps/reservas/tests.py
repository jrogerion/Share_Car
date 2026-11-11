from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.administracao.models import ConfiguracaoComissao
from apps.contas.models import Usuario
from apps.veiculos.models import PeriodoAgenda, Veiculo

from .models import Reserva
from .services import ReservaInvalida, criar_reserva


class ReservaBaseTests(TestCase):
    """Dados compartilhados pelos testes de disponibilidade e reserva."""

    @classmethod
    def setUpTestData(cls):
        ConfiguracaoComissao.objects.update_or_create(
            pk=1,
            defaults={"percentual": "15.00"},
        )
        cls.proprietario = Usuario.objects.create_user(
            username="proprietario",
            email="proprietario@example.com",
            password="senha-de-teste",
        )
        cls.locatario = Usuario.objects.create_user(
            username="locatario",
            email="locatario@example.com",
            password="senha-de-teste",
            locatario=True, aprovacao_cnh="aprovado", cnh_numero="CNH-TESTE-001",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.outro = Usuario.objects.create_user(
            username="outro",
            email="outro@example.com",
            password="senha-de-teste",
            locatario=True, aprovacao_cnh="aprovado", cnh_numero="CNH-TESTE-002",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.veiculo = cls.criar_veiculo()
        cls.veiculo2 = cls.criar_veiculo(cidade="Campinas")

    @classmethod
    def criar_veiculo(cls, **dados):
        padrao = {
            "proprietario": cls.proprietario,
            "caracteristicas": "Veículo de teste",
            "cidade": "São Paulo",
            "categoria": "Hatch",
            "cambio": "Manual",
            "combustivel": "Flex",
            "passageiros": 5,
            "preco_diaria": Decimal("150.00"),
            "ativo": True,
            "bloqueado": False,
            "aprovacao": Veiculo.Aprovacao.APROVADO,
        }
        padrao.update(dados)
        return Veiculo.objects.create(**padrao)

    @classmethod
    def periodo(cls, dias_inicio=5, duracao=3):
        inicio = timezone.localdate() + timedelta(days=dias_inicio)
        return inicio, inicio + timedelta(days=duracao)

    @classmethod
    def criar_reserva_direta(
        cls,
        *,
        veiculo=None,
        locatario=None,
        inicio=None,
        fim=None,
        status=Reserva.Status.SOLICITADA,
    ):
        veiculo = veiculo or cls.veiculo
        locatario = locatario or cls.locatario
        inicio = inicio or (timezone.localdate() + timedelta(days=5))
        fim = fim or (inicio + timedelta(days=3))
        dias = (fim - inicio).days
        valor = (veiculo.preco_diaria * dias).quantize(Decimal("0.01"))
        return Reserva.objects.create(
            veiculo=veiculo,
            locatario=locatario,
            inicio=inicio,
            fim=fim,
            status=status,
            preco_diaria=veiculo.preco_diaria,
            valor_diarias=valor,
            taxas=Decimal("0.00"),
            total=valor,
            percentual_comissao=Decimal("15.00"),
        )


class DisponibilidadeTests(ReservaBaseTests):
    """A busca deve considerar agenda, reservas e disponibilidade cadastrada."""

    def buscar(self, **filtros):
        return self.client.get(reverse("core:resultados"), filtros)

    def test_busca_sem_periodo_ignora_agenda(self):
        self.criar_reserva_direta()

        response = self.buscar()

        self.assertContains(response, "Hatch em São Paulo")
        self.assertContains(response, "Hatch em Campinas")

    def test_periodo_livre_exibe_veiculo(self):
        inicio, fim = self.periodo()

        response = self.buscar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertContains(response, "Hatch em São Paulo")
        self.assertContains(response, "Hatch em Campinas")

    def test_reserva_sobreposta_remove_veiculo_da_busca(self):
        inicio, fim = self.periodo()
        self.criar_reserva_direta(inicio=inicio, fim=fim)

        response = self.buscar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertContains(response, "Hatch em Campinas")
        self.assertNotContains(response, "Hatch em São Paulo")

    def test_reserva_cancelada_libera_o_periodo(self):
        inicio, fim = self.periodo()
        self.criar_reserva_direta(
            inicio=inicio,
            fim=fim,
            status=Reserva.Status.CANCELADA,
        )

        response = self.buscar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertContains(response, "Hatch em São Paulo")

    def test_bloqueio_prevalece_sobre_disponibilidade(self):
        inicio, fim = self.periodo()
        PeriodoAgenda.objects.create(
            veiculo=self.veiculo,
            inicio=inicio,
            fim=fim,
            tipo=PeriodoAgenda.Tipo.DISPONIVEL,
        )
        PeriodoAgenda.objects.create(
            veiculo=self.veiculo,
            inicio=inicio,
            fim=fim,
            tipo=PeriodoAgenda.Tipo.BLOQUEADO,
        )

        response = self.buscar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertContains(response, "Hatch em Campinas")
        self.assertNotContains(response, "Hatch em São Paulo")

    def test_fora_da_disponibilidade_cadastrada_remove_veiculo(self):
        base = timezone.localdate()
        PeriodoAgenda.objects.create(
            veiculo=self.veiculo,
            inicio=base,
            fim=base + timedelta(days=5),
            tipo=PeriodoAgenda.Tipo.DISPONIVEL,
        )
        inicio, fim = self.periodo(dias_inicio=10, duracao=2)

        response = self.buscar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertContains(response, "Hatch em Campinas")
        self.assertNotContains(response, "Hatch em São Paulo")

    def test_dentro_da_disponibilidade_cadastrada_mantem_veiculo(self):
        base = timezone.localdate()
        PeriodoAgenda.objects.create(
            veiculo=self.veiculo,
            inicio=base,
            fim=base + timedelta(days=10),
            tipo=PeriodoAgenda.Tipo.DISPONIVEL,
        )
        inicio, fim = self.periodo(dias_inicio=2, duracao=2)

        response = self.buscar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertContains(response, "Hatch em São Paulo")

    def test_periodo_invertido_mostra_erro(self):
        inicio, fim = self.periodo()

        response = self.buscar(
            retirada=fim.isoformat(),
            devolucao=inicio.isoformat(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível aplicar os filtros.")
        self.assertContains(
            response,
            "A devolução deve ser posterior à retirada.",
        )

    def test_apenas_uma_data_mostra_erro(self):
        inicio, _ = self.periodo()

        response = self.buscar(retirada=inicio.isoformat())

        self.assertContains(response, "Informe a retirada e a devolução juntas.")


class CriacaoReservaTests(ReservaBaseTests):
    """O fluxo real de solicitação deve validar autenticação e disponibilidade."""

    def criar(self, veiculo=None, inicio=None, fim=None):
        veiculo = veiculo or self.veiculo
        inicio = inicio or (timezone.localdate() + timedelta(days=5))
        fim = fim or (inicio + timedelta(days=3))
        return self.client.post(
            reverse("reservas:criar", args=[veiculo.pk]),
            {"retirada": inicio.isoformat(), "devolucao": fim.isoformat()},
        )

    def test_criacao_exige_autenticacao(self):
        response = self.criar()

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:entrar"), response.url)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_locatario_cria_solicitacao_com_valores_reais(self):
        self.client.force_login(self.locatario)
        inicio, fim = self.periodo()

        response = self.criar(inicio=inicio, fim=fim)

        reserva = Reserva.objects.get()
        self.assertRedirects(
            response,
            reverse("reservas:detalhe", args=[reserva.pk]),
        )
        self.assertEqual(reserva.veiculo, self.veiculo)
        self.assertEqual(reserva.locatario, self.locatario)
        self.assertEqual(reserva.status, Reserva.Status.SOLICITADA)
        self.assertEqual(reserva.dias, 3)
        self.assertEqual(reserva.preco_diaria, Decimal("150.00"))
        self.assertEqual(reserva.valor_diarias, Decimal("450.00"))
        self.assertEqual(reserva.total, Decimal("450.00"))
        self.assertEqual(reserva.percentual_comissao, Decimal("15.00"))
        self.assertEqual(reserva.comissao, Decimal("67.50"))
        self.assertEqual(reserva.repasse_proprietario, Decimal("382.50"))

    def test_proprietario_nao_reserva_o_proprio_veiculo(self):
        self.client.force_login(self.proprietario)
        inicio, fim = self.periodo()

        response = self.criar(inicio=inicio, fim=fim, veiculo=self.veiculo)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 0)
        # A mensagem é exibida após o redirecionamento.
        resposta_final = self.client.get(response.url)
        self.assertContains(resposta_final, "próprio veículo")

    def test_periodo_ocupado_nao_cria_nova_reserva(self):
        inicio, fim = self.periodo()
        self.criar_reserva_direta(inicio=inicio, fim=fim)
        self.client.force_login(self.outro)

        response = self.criar(inicio=inicio, fim=fim)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 1)
        resposta_final = self.client.get(response.url)
        self.assertContains(resposta_final, "já possui uma reserva")

    def test_veiculo_nao_publico_retorna_404(self):
        pendente = self.criar_veiculo(
            aprovacao=Veiculo.Aprovacao.PENDENTE,
        )
        self.client.force_login(self.locatario)

        response = self.criar(veiculo=pendente)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_datas_invalidas_nao_criam_reserva(self):
        self.client.force_login(self.locatario)
        inicio, fim = self.periodo()

        response = self.criar(inicio=fim, fim=inicio)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 0)
        resposta_final = self.client.get(response.url)
        self.assertContains(
            resposta_final,
            "A devolução deve ser posterior à retirada.",
        )

    def test_pagina_de_detalhes_estima_valores_do_periodo(self):
        inicio, fim = self.periodo()
        url = reverse("core:detalhes", args=[self.veiculo.pk])

        response = self.client.get(
            url,
            {"retirada": inicio.isoformat(), "devolucao": fim.isoformat()},
        )

        self.assertContains(response, "Disponível no período informado.")
        self.assertContains(response, "3 diárias")
        self.assertContains(response, "R$ 450,00")
        self.assertContains(response, "Comissão de 15,00%")
        self.assertContains(response, "R$ 67,50")
        self.assertContains(response, "Entrar para solicitar")

    def test_detalhes_indicam_indisponibilidade(self):
        inicio, fim = self.periodo()
        self.criar_reserva_direta(inicio=inicio, fim=fim)
        url = reverse("core:detalhes", args=[self.veiculo.pk])

        response = self.client.get(
            url,
            {"retirada": inicio.isoformat(), "devolucao": fim.isoformat()},
        )

        self.assertContains(response, "já possui uma reserva")
        self.assertNotContains(response, "Solicitar reserva")


class GestaoReservaTests(ReservaBaseTests):
    """Aceite, recusa e cancelamento devem respeitar os papéis da reserva."""

    def acao(self, reserva, nome):
        return self.client.post(
            reverse(f"reservas:{nome}", args=[reserva.pk]),
        )

    def test_proprietario_aceita_solicitacao(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.proprietario)

        response = self.acao(reserva, "aceitar")

        self.assertRedirects(
            response,
            reverse("reservas:detalhe", args=[reserva.pk]),
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.ACEITA)

    def test_proprietario_recusa_solicitacao(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.proprietario)

        self.acao(reserva, "recusar")

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.RECUSADA)

    def test_locatario_nao_pode_aceitar(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.locatario)

        response = self.acao(reserva, "aceitar")

        self.assertEqual(response.status_code, 404)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.SOLICITADA)

    def test_locatario_cancela_reserva(self):
        reserva = self.criar_reserva_direta(
            status=Reserva.Status.ACEITA,
        )
        self.client.force_login(self.locatario)

        self.acao(reserva, "cancelar")

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)

    def test_outro_usuario_nao_cancela(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.outro)

        response = self.acao(reserva, "cancelar")

        self.assertEqual(response.status_code, 404)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.SOLICITADA)

    def test_aceite_repetido_nao_altera_status(self):
        reserva = self.criar_reserva_direta(status=Reserva.Status.ACEITA)
        self.client.force_login(self.proprietario)

        self.acao(reserva, "aceitar")

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.ACEITA)

    def test_acoes_exigem_post(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.proprietario)

        response = self.client.get(
            reverse("reservas:aceitar", args=[reserva.pk]),
        )

        self.assertEqual(response.status_code, 405)

    def test_reserva_so_aparece_para_participantes(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.outro)

        response = self.client.get(
            reverse("reservas:detalhe", args=[reserva.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_detalhe_nao_expoe_email_dos_participantes(self):
        reserva = self.criar_reserva_direta()
        self.client.force_login(self.locatario)

        response = self.client.get(
            reverse("reservas:detalhe", args=[reserva.pk]),
        )

        self.assertContains(response, "R$ 450,00")
        self.assertContains(response, "locatario")
        self.assertContains(response, "proprietario")
        self.assertNotContains(response, "locatario@example.com")
        self.assertNotContains(response, "proprietario@example.com")

    def test_minhas_reservas_separa_locatario_e_proprietario(self):
        reserva = self.criar_reserva_direta()

        self.client.force_login(self.locatario)
        response = self.client.get(reverse("reservas:minhas"))
        self.assertContains(response, "Como locatário")
        self.assertContains(response, "Hatch em São Paulo")
        self.assertContains(response, "1 reserva")

        self.client.force_login(self.proprietario)
        response = self.client.get(reverse("reservas:minhas"))
        self.assertContains(response, "Como proprietário")
        self.assertContains(response, "Locatário: locatario")
        self.assertContains(response, "Meus veículos")
        self.assertContains(
            response,
            reverse("reservas:agenda", args=[self.veiculo.pk]),
        )
        self.assertEqual(len(response.context["como_proprietario"]), 1)
        self.assertEqual(len(response.context["como_locatario"]), 0)
        self.assertContains(response, str(reserva.pk))

    def test_minhas_reservas_exige_autenticacao(self):
        response = self.client.get(reverse("reservas:minhas"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:entrar"), response.url)


class ServicoReservaTests(ReservaBaseTests):
    """O serviço centraliza a criação e as transições de status."""

    def test_criar_reserva_usa_comissao_configurada(self):
        ConfiguracaoComissao.objects.filter(pk=1).update(
            percentual=Decimal("10.00"),
        )
        inicio, fim = self.periodo()

        reserva = criar_reserva(
            veiculo=self.veiculo,
            locatario=self.locatario,
            inicio=inicio,
            fim=fim,
        )

        self.assertEqual(reserva.percentual_comissao, Decimal("10.00"))
        self.assertEqual(reserva.comissao, Decimal("45.00"))
        self.assertEqual(reserva.repasse_proprietario, Decimal("405.00"))

    def test_criar_reserva_recusa_periodo_invalido(self):
        inicio, fim = self.periodo()

        with self.assertRaisesMessage(ReservaInvalida, "posterior"):
            criar_reserva(
                veiculo=self.veiculo,
                locatario=self.locatario,
                inicio=fim,
                fim=inicio,
            )

    def test_criar_reserva_recusa_veiculo_do_proprio_locatario(self):
        inicio, fim = self.periodo()

        with self.assertRaisesMessage(ReservaInvalida, "próprio veículo"):
            criar_reserva(
                veiculo=self.veiculo,
                locatario=self.proprietario,
                inicio=inicio,
                fim=fim,
            )


class AgendaVeiculoTests(ReservaBaseTests):
    """O proprietário deve poder cadastrar disponibilidade e bloqueios."""

    def agenda(self, veiculo=None):
        return reverse(
            "reservas:agenda",
            args=[(veiculo or self.veiculo).pk],
        )

    def adicionar(self, inicio, fim, tipo=PeriodoAgenda.Tipo.DISPONIVEL):
        return self.client.post(
            self.agenda(),
            {
                "inicio": inicio.isoformat(),
                "fim": fim.isoformat(),
                "tipo": tipo,
            },
        )

    def test_agenda_exige_autenticacao(self):
        response = self.client.get(self.agenda())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:entrar"), response.url)

    def test_outro_usuario_nao_gerencia_agenda(self):
        self.client.force_login(self.outro)

        response = self.client.get(self.agenda())

        self.assertEqual(response.status_code, 404)

    def test_proprietario_ve_a_agenda_do_proprio_veiculo(self):
        self.client.force_login(self.proprietario)

        response = self.client.get(self.agenda())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reservas/agenda.html")
        self.assertContains(response, "Disponibilidade de Hatch em São Paulo")
        self.assertContains(response, "Nenhum período cadastrado")

    def test_proprietario_cadastra_disponibilidade(self):
        self.client.force_login(self.proprietario)
        inicio, fim = self.periodo()

        response = self.adicionar(inicio, fim)

        self.assertRedirects(response, self.agenda())
        periodo = PeriodoAgenda.objects.get()
        self.assertEqual(periodo.veiculo, self.veiculo)
        self.assertEqual(periodo.tipo, PeriodoAgenda.Tipo.DISPONIVEL)
        self.assertEqual(periodo.inicio, inicio)
        self.assertEqual(periodo.fim, fim)

    def test_proprietario_cadastra_bloqueio(self):
        self.client.force_login(self.proprietario)
        inicio, fim = self.periodo()

        self.adicionar(inicio, fim, PeriodoAgenda.Tipo.BLOQUEADO)

        periodo = PeriodoAgenda.objects.get()
        self.assertEqual(periodo.tipo, PeriodoAgenda.Tipo.BLOQUEADO)

    def test_periodo_invertido_nao_e_cadastrado(self):
        self.client.force_login(self.proprietario)
        inicio, fim = self.periodo()

        response = self.adicionar(fim, inicio)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "O fim deve ser posterior ao início do período.",
        )
        self.assertEqual(PeriodoAgenda.objects.count(), 0)

    def test_proprietario_remove_periodo(self):
        self.client.force_login(self.proprietario)
        inicio, fim = self.periodo()
        periodo = PeriodoAgenda.objects.create(
            veiculo=self.veiculo,
            inicio=inicio,
            fim=fim,
            tipo=PeriodoAgenda.Tipo.BLOQUEADO,
        )

        response = self.client.post(
            reverse("reservas:remover_periodo", args=[periodo.pk]),
        )

        self.assertRedirects(response, self.agenda())
        self.assertFalse(PeriodoAgenda.objects.filter(pk=periodo.pk).exists())

    def test_outro_usuario_nao_remove_periodo(self):
        inicio, fim = self.periodo()
        periodo = PeriodoAgenda.objects.create(
            veiculo=self.veiculo,
            inicio=inicio,
            fim=fim,
            tipo=PeriodoAgenda.Tipo.BLOQUEADO,
        )
        self.client.force_login(self.outro)

        response = self.client.post(
            reverse("reservas:remover_periodo", args=[periodo.pk]),
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PeriodoAgenda.objects.filter(pk=periodo.pk).exists())

    def test_bloqueio_cadastrado_pela_agenda_remove_veiculo_da_busca(self):
        self.client.force_login(self.proprietario)
        inicio, fim = self.periodo()
        self.adicionar(inicio, fim, PeriodoAgenda.Tipo.BLOQUEADO)

        response = self.client.get(
            reverse("core:resultados"),
            {"retirada": inicio.isoformat(), "devolucao": fim.isoformat()},
        )

        self.assertNotContains(response, "Hatch em São Paulo")
        self.assertContains(response, "Hatch em Campinas")

    def test_detalhes_do_proprietario_oferecem_gestao_da_agenda(self):
        self.client.force_login(self.proprietario)

        response = self.client.get(
            reverse("core:detalhes", args=[self.veiculo.pk]),
        )

        self.assertContains(response, "Gerenciar disponibilidade")
        self.assertContains(response, self.agenda())
