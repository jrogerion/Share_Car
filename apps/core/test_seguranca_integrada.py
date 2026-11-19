from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.administracao.models import ConfiguracaoComissao
from apps.avaliacoes.models import Avaliacao
from apps.contas.models import Usuario
from apps.locacoes.models import FotoRegistroLocacao, RegistroLocacao
from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva
from apps.veiculos.models import FotoVeiculo, PeriodoAgenda, Veiculo


class SegurancaIntegradaTests(TestCase):
    """Requisições adversariais pelas URLs reais, somente em banco de teste."""

    @classmethod
    def setUpTestData(cls):
        cls.senha = "SenhaFicticia!72rT9"
        cls.dono = Usuario.objects.create_user(
            "seg-dono", "dono@seg.example.com", first_name="Dono", last_name="Fictício",
            proprietario=True, aprovacao_documento="aprovado",
        )
        cls.locatario = Usuario.objects.create_user(
            "seg-locatario", "locatario@seg.example.com", cls.senha,
            first_name="Locatário", last_name="Fictício", locatario=True,
            cnh_numero="CNH-FICTICIA", aprovacao_cnh="aprovado",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.terceiro = Usuario.objects.create_user("seg-terceiro", "terceiro@seg.example.com", locatario=True)
        cls.staff = Usuario.objects.create_user("seg-staff", "staff@seg.example.com", is_staff=True)
        cls.admin = Usuario.objects.create_superuser("seg-admin", "admin@seg.example.com", cls.senha)
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.dono, caracteristicas="Veículo fictício",
            cidade="Campinas", categoria="Hatch", cambio="Manual", combustivel="Flex",
            passageiros=5, preco_diaria="150.00", aprovacao="aprovado",
        )
        for indice, status in enumerate(("solicitada", "aceita", "em_andamento", "concluida")):
            inicio = timezone.localdate() + timedelta(days=5 + indice * 5)
            reserva = Reserva.objects.create(
                veiculo=cls.veiculo, locatario=cls.locatario, inicio=inicio,
                fim=inicio + timedelta(days=3), status=status, preco_diaria="150.00",
                valor_diarias="450.00", taxas=0, total="450.00", percentual_comissao="15.00",
            )
            setattr(cls, status, reserva)
            if status in ("em_andamento", "concluida"):
                Pagamento.objects.create(
                    reserva=reserva, meio="pix", status="aprovado", valor_bruto="450.00",
                    comissao="67.50", repasse_proprietario="382.50",
                )
                registro = RegistroLocacao.objects.create(
                    reserva=reserva, tipo="check_in", quilometragem=1000, nivel_combustivel=80,
                )
                if status == "concluida":
                    cls.registro = registro
                    RegistroLocacao.objects.create(
                        reserva=reserva, tipo="check_out", quilometragem=1100, nivel_combustivel=70,
                    )
        inicio = timezone.localdate() + timedelta(days=60)
        cls.paga = Reserva.objects.create(
            veiculo=cls.veiculo, locatario=cls.locatario,
            inicio=inicio - timedelta(days=10), fim=inicio - timedelta(days=7),
            status="aceita", preco_diaria="150.00", valor_diarias="450.00",
            taxas=0, total="450.00", percentual_comissao="15.00",
        )
        Pagamento.objects.create(
            reserva=cls.paga, meio="pix", status="aprovado", valor_bruto="450.00",
            comissao="67.50", repasse_proprietario="382.50",
        )
        cls.periodo = PeriodoAgenda.objects.create(
            veiculo=cls.veiculo, inicio=inicio, fim=inicio + timedelta(days=2), tipo="bloqueado",
        )
        ConfiguracaoComissao.objects.update_or_create(pk=1, defaults={"percentual": "15.00"})

    def setUp(self):
        for model, campo in ((Usuario, "documento_identidade"), (FotoRegistroLocacao, "foto"), (FotoVeiculo, "foto")):
            self.enterContext(patch.object(model._meta.get_field(campo), "storage", InMemoryStorage()))
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "blue").save(buffer, format="PNG")
        conteudo = buffer.getvalue()
        self.dono.documento_identidade = SimpleUploadedFile("doc-ficticio.png", conteudo, "image/png")
        self.dono.save(update_fields=["documento_identidade"])
        self.foto = FotoRegistroLocacao.objects.create(
            registro=self.registro, foto=SimpleUploadedFile("vistoria-ficticia.png", conteudo, "image/png"),
        )

    def estado(self):
        estado = {"usuarios": list(Usuario.objects.order_by("pk").values(
            "id", "username", "email", "first_name", "last_name", "password",
            "is_active", "is_staff", "is_superuser", "aprovacao_documento", "aprovacao_cnh",
            "documento_identidade", "cnh_numero", "cnh_validade", "locatario", "proprietario",
        ))}
        for model in (Veiculo, Reserva, Pagamento, RegistroLocacao, FotoRegistroLocacao, FotoVeiculo, PeriodoAgenda, Avaliacao, ConfiguracaoComissao, LogEntry):
            estado[model._meta.label] = list(model.objects.order_by("pk").values())
        return estado

    def test_terceiros_nao_consultam_nem_alteram_objetos_alheios(self):
        self.client.force_login(self.terceiro)
        antes = self.estado()
        rotas = (
            ("reservas:detalhe", [self.aceita.pk]),
            ("reservas:aceitar", [self.solicitada.pk]),
            ("reservas:recusar", [self.solicitada.pk]),
            ("reservas:cancelar", [self.aceita.pk]),
            ("reservas:agenda", [self.veiculo.pk]),
            ("reservas:remover_periodo", [self.periodo.pk]),
            ("veiculos:editar", [self.veiculo.pk]),
            ("veiculos:fotos", [self.veiculo.pk]),
            ("pagamentos:pagar", [self.aceita.pk]),
            ("locacoes:check_in", [self.aceita.pk]),
            ("locacoes:check_out", [self.em_andamento.pk]),
            ("avaliacoes:avaliar", [self.concluida.pk]),
        )
        for nome, args in rotas:
            # Ações exclusivamente POST podem responder 405 a GET, sem revelar dados.
            with self.subTest(rota=nome):
                self.assertIn(self.client.get(reverse(nome, args=args)).status_code, (404, 405))
                esperado = 405 if nome == "reservas:detalhe" else 404
                self.assertEqual(self.client.post(reverse(nome, args=args), {}).status_code, esperado)
        self.assertEqual(self.estado(), antes)

    def test_participantes_nao_assumem_acoes_da_outra_parte(self):
        casos = (
            (self.locatario, "reservas:aceitar", self.solicitada.pk),
            (self.locatario, "reservas:recusar", self.solicitada.pk),
            (self.locatario, "veiculos:editar", self.veiculo.pk),
            (self.dono, "reservas:cancelar", self.aceita.pk),
            (self.dono, "pagamentos:pagar", self.aceita.pk),
            (self.dono, "locacoes:check_in", self.aceita.pk),
            (self.dono, "locacoes:check_out", self.em_andamento.pk),
        )
        for usuario, nome, pk in casos:
            with self.subTest(rota=nome, papel=usuario.pk):
                self.client.force_login(usuario)
                antes = self.estado()
                self.assertEqual(self.client.post(reverse(nome, args=[pk]), {}).status_code, 404)
                self.assertEqual(self.estado(), antes)

    def test_operacoes_mutaveis_exigem_csrf(self):
        casos = (
            (self.admin, "administracao:veiculo", [self.veiculo.pk, "aprovar"]),
            (self.admin, "administracao:documento", [self.dono.pk, "aprovar"]),
            (self.admin, "administracao:cnh", [self.locatario.pk, "aprovar"]),
            (self.admin, "administracao:bloqueio_usuario", [self.terceiro.pk]),
            (self.admin, "administracao:bloqueio_veiculo", [self.veiculo.pk]),
            (self.admin, "administracao:comissao", []),
            (self.dono, "core:veiculo", []),
            (self.dono, "veiculos:editar", [self.veiculo.pk]),
            (self.dono, "veiculos:fotos", [self.veiculo.pk]),
            (self.locatario, "contas:perfil", []),
            (self.locatario, "contas:enviar_documento", []),
            (self.locatario, "reservas:criar", [self.veiculo.pk]),
            (self.dono, "reservas:aceitar", [self.solicitada.pk]),
            (self.dono, "reservas:recusar", [self.solicitada.pk]),
            (self.locatario, "reservas:cancelar", [self.aceita.pk]),
            (self.dono, "reservas:agenda", [self.veiculo.pk]),
            (self.dono, "reservas:remover_periodo", [self.periodo.pk]),
            (self.locatario, "pagamentos:pagar", [self.aceita.pk]),
            (self.locatario, "locacoes:check_in", [self.paga.pk]),
            (self.locatario, "locacoes:check_out", [self.em_andamento.pk]),
            (self.locatario, "avaliacoes:avaliar", [self.concluida.pk]),
            (self.locatario, "contas:alterar_senha", []),
            (self.locatario, "core:sair", []),
        )
        for usuario, nome, args in casos:
            client = Client(enforce_csrf_checks=True)
            client.force_login(usuario)
            antes = self.estado()
            for payload in ({}, {"csrfmiddlewaretoken": "token-invalido"}):
                with self.subTest(rota=nome, token=bool(payload)):
                    self.assertEqual(client.post(reverse(nome, args=args), payload).status_code, 403)
            self.assertEqual(self.estado(), antes)

    def test_token_valido_nao_autoriza_origem_externa(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.locatario)
        client.get(reverse("contas:perfil"))
        antes = self.estado()
        response = client.post(reverse("contas:perfil"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "first_name": "Adulterado", "last_name": "Fictício", "locatario": "on",
        }, HTTP_ORIGIN="https://intruso.example")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_get_nao_executa_transicoes(self):
        for usuario, nome, args in (
            (self.dono, "reservas:aceitar", [self.solicitada.pk]),
            (self.dono, "reservas:recusar", [self.solicitada.pk]),
            (self.locatario, "reservas:cancelar", [self.aceita.pk]),
            (self.dono, "reservas:remover_periodo", [self.periodo.pk]),
            (self.admin, "administracao:bloqueio_usuario", [self.terceiro.pk]),
            (self.admin, "administracao:bloqueio_veiculo", [self.veiculo.pk]),
            (self.admin, "administracao:veiculo", [self.veiculo.pk, "aprovar"]),
        ):
            self.client.force_login(usuario)
            antes = self.estado()
            with self.subTest(rota=nome):
                self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 405)
                self.assertEqual(self.estado(), antes)

    def test_paginas_privadas_nao_podem_ser_armazenadas_em_cache(self):
        casos = (
            (self.locatario, "contas:perfil", []),
            (self.locatario, "contas:painel", []),
            (self.locatario, "contas:alterar_senha", []),
            (self.locatario, "contas:alterar_senha_concluido", []),
            (self.locatario, "reservas:minhas", []),
            (self.locatario, "reservas:detalhe", [self.aceita.pk]),
            (self.locatario, "pagamentos:pagar", [self.aceita.pk]),
            (self.locatario, "locacoes:check_in", [self.paga.pk]),
            (self.locatario, "locacoes:check_out", [self.em_andamento.pk]),
            (self.locatario, "avaliacoes:avaliar", [self.concluida.pk]),
            (self.dono, "veiculos:meus", []),
            (self.admin, "administracao:painel", []),
            (self.admin, "administracao:comissao", []),
            (self.admin, "administracao:reserva", [self.concluida.pk]),
        )
        for usuario, nome, args in casos:
            with self.subTest(rota=nome):
                self.client.force_login(usuario)
                response = self.client.get(reverse(nome, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response.get("Cache-Control", ""), nome)

    def test_headers_e_parametros_nao_contornam_autorizacao_de_download(self):
        self.client.force_login(self.terceiro)
        for nome, pk in (
            ("locacoes:foto", self.foto.pk),
            ("contas:documento_identidade", self.dono.pk),
            ("contas_legacy:documento_identidade", self.dono.pk),
        ):
            with self.subTest(rota=nome):
                response = self.client.get(reverse(nome, args=[pk]), {
                    "usuario_id": self.dono.pk, "download": "1", "is_superuser": "1",
                }, HTTP_RANGE="bytes=0-1", HTTP_IF_NONE_MATCH="*")
                self.assertEqual(response.status_code, 404)

    def test_logout_revoga_acesso_a_foto_e_get_nao_desloga(self):
        self.client.force_login(self.locatario)
        url = reverse("locacoes:foto", args=[self.foto.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        b"".join(response.streaming_content)
        self.assertEqual(self.client.get(reverse("core:sair")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("core:sair"))
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_conta_bloqueada_perde_acesso_a_sessao_existente(self):
        self.client.force_login(self.locatario)
        Usuario.objects.filter(pk=self.locatario.pk).update(is_active=False)
        response = self.client.get(reverse("reservas:detalhe", args=[self.aceita.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("locacoes:foto", args=[self.foto.pk])).status_code, 302)

    def test_api_publica_nao_expoe_dados_privados_nem_permite_escrita(self):
        url = reverse("veiculos_api:detalhe", args=[self.veiculo.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {
            "id", "categoria", "cidade", "cambio", "combustivel", "passageiros",
            "preco_diaria", "caracteristicas", "fotos",
        })
        antes = self.estado()
        self.assertEqual(self.client.post(reverse("veiculos_api:lista"), {"proprietario": self.terceiro.pk}).status_code, 405)
        self.assertEqual(self.client.patch(url, "{}", content_type="application/json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(self.estado(), antes)

    def test_valores_forjados_nao_alteram_condicoes_financeiras(self):
        self.client.force_login(self.locatario)
        self.client.post(reverse("pagamentos:pagar", args=[self.aceita.pk]), {
            "meio": "cartao", "parcelas": "8", "resultado": "aprovado",
            "valor_bruto": "0.01", "juros": "0", "desconto": "449.99",
            "comissao": "0", "repasse_proprietario": "0.01", "reserva": self.solicitada.pk,
        })
        pagamento = Pagamento.objects.get(reserva=self.aceita)
        self.aceita.refresh_from_db()
        self.assertEqual(pagamento.valor_bruto, self.aceita.total)
        self.assertEqual(pagamento.juros, 36)
        self.assertEqual(pagamento.desconto, 0)
        self.assertEqual(pagamento.comissao, self.aceita.comissao)
        self.assertFalse(Pagamento.objects.filter(reserva=self.solicitada).exists())

    def test_busca_trata_payload_sql_como_texto(self):
        antes = self.estado()
        response = self.client.get(reverse("veiculos_api:lista"), {"cidade": "' OR 1=1 --"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(self.estado(), antes)
