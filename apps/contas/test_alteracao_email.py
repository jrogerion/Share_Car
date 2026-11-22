import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .models import AlteracaoEmail, LimiteAcesso, Usuario
from .services import confirmar_alteracao_email, solicitar_alteracao_email


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlteracaoEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.senha = "SenhaFicticia!72rT9"
        cls.usuario = Usuario.objects.create_user(
            "email-ficticio", "atual@example.com", cls.senha,
            first_name="Pessoa", last_name="Fictícia", locatario=True,
        )
        cls.outro = Usuario.objects.create_user(
            "outro-email-ficticio", "outro@example.com", cls.senha,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def solicitar(self, email="novo@example.com", **dados):
        return self.client.post(reverse("contas:alterar_email"), {
            "novo_email": email, "senha_atual": self.senha, **dados,
        })

    def link(self):
        return urlsplit(re.search(r"https?://\S+", mail.outbox[-1].body).group()).path

    def token(self):
        return resolve(self.link()).kwargs["token"]

    def abrir_confirmacao(self, client=None):
        client = client or self.client
        self.assertRedirects(client.get(self.link()), reverse("contas:confirmar_email"))

    def test_solicitacao_nao_muda_login_e_armazena_somente_hash(self):
        response = self.solicitar(" NOVO@EXAMPLE.COM ")
        self.assertRedirects(response, reverse("contas:alterar_email"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")
        pedido = AlteracaoEmail.objects.get(usuario=self.usuario)
        self.assertEqual(pedido.novo_email, "novo@example.com")
        self.assertEqual(mail.outbox[0].to, ["novo@example.com"])
        self.assertEqual(pedido.token_hash, hashlib.sha256(self.token().encode()).hexdigest())
        self.assertNotEqual(pedido.assinatura_conta, self.usuario.password)
        self.assertGreater(pedido.expira_em, timezone.now() + timedelta(minutes=59))
        self.assertLess(pedido.expira_em, timezone.now() + timedelta(minutes=61))

    def test_perfil_oferece_alteracao_separada(self):
        response = self.client.get(reverse("contas:perfil"))
        self.assertContains(response, reverse("contas:alterar_email"))

    def test_senha_errada_nao_envia_nem_cria_solicitacao(self):
        response = self.solicitar(senha_atual="NaoExibirEstaSenha!42")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "NaoExibirEstaSenha!42")
        self.assertIn("senha_atual", response.wsgi_request.sensitive_post_parameters)
        self.assertFalse(AlteracaoEmail.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_endereco_existente_ignora_caixa_e_espacos(self):
        response = self.solicitar(" OUTRO@EXAMPLE.COM ")
        self.assertContains(response, "Não é possível usar este e-mail.")
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_email_de_conta_inativa_tambem_esta_reservado(self):
        Usuario.objects.filter(pk=self.outro.pk).update(is_active=False)
        self.assertEqual(self.solicitar(self.outro.email).status_code, 200)
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_endereco_atual_e_rejeitado(self):
        response = self.solicitar(" ATUAL@EXAMPLE.COM ")
        self.assertContains(response, "Informe um e-mail diferente do atual.")
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_email_invalido_e_rejeitado(self):
        response = self.solicitar("nao-e-email")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_get_nao_confirma_e_token_nao_aparece_na_pagina_final(self):
        self.solicitar()
        token = self.token()
        self.abrir_confirmacao()
        response = self.client.get(reverse("contas:confirmar_email"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, token)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")
        self.assertTrue(AlteracaoEmail.objects.filter(usuario=self.usuario).exists())

    def test_confirmacao_troca_login_preserva_conta_e_roda_sessao(self):
        senha_hash = self.usuario.password
        self.solicitar()
        self.abrir_confirmacao()
        sessao_anterior = self.client.session.session_key
        response = self.client.post(reverse("contas:confirmar_email"), {
            "email": self.outro.email, "usuario": self.outro.pk, "is_staff": "on",
        })
        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "novo@example.com")
        self.assertEqual(self.usuario.password, senha_hash)
        self.assertTrue(self.usuario.locatario)
        self.assertFalse(self.usuario.is_staff)
        self.assertFalse(AlteracaoEmail.objects.exists())
        self.assertNotEqual(self.client.session.session_key, sessao_anterior)
        visitante = Client()
        self.assertEqual(visitante.post(reverse("core:entrar"), {
            "username": "atual@example.com", "password": self.senha,
        }).status_code, 200)
        self.assertEqual(visitante.post(reverse("core:entrar"), {
            "username": "novo@example.com", "password": self.senha,
        }).status_code, 302)

    def test_link_ja_utilizado_nao_pode_ser_repetido(self):
        self.solicitar()
        link = self.link()
        self.abrir_confirmacao()
        self.client.post(reverse("contas:confirmar_email"))
        self.assertEqual(self.client.get(link).status_code, 400)
        self.assertEqual(self.client.post(reverse("contas:confirmar_email")).status_code, 400)

    def test_confirmacao_preserva_reserva_e_identidade_do_locatario(self):
        carro = Veiculo.objects.create(
            proprietario=self.outro, caracteristicas="Veículo fictício",
            cidade="Campinas", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="150.00",
        )
        inicio = timezone.localdate() + timedelta(days=3)
        Reserva.objects.create(
            veiculo=carro, locatario=self.usuario, inicio=inicio,
            fim=inicio + timedelta(days=1), status="solicitada",
            preco_diaria="150.00", valor_diarias="150.00", taxas=0,
            total="150.00", percentual_comissao="15.00",
        )
        antes = list(Reserva.objects.values())
        self.solicitar()
        self.abrir_confirmacao()
        self.client.post(reverse("contas:confirmar_email"))
        self.assertEqual(list(Reserva.objects.values()), antes)
        self.assertEqual(Reserva.objects.get().locatario_id, self.usuario.pk)

    def test_nova_solicitacao_invalida_link_anterior(self):
        self.solicitar()
        anterior = self.link()
        self.solicitar("segundo@example.com")
        self.assertEqual(self.client.get(anterior).status_code, 400)
        self.abrir_confirmacao()
        self.client.post(reverse("contas:confirmar_email"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "segundo@example.com")

    def test_link_expira_em_uma_hora(self):
        self.solicitar()
        deadline = AlteracaoEmail.objects.get().expira_em
        with patch("apps.contas.services.timezone.now", return_value=deadline):
            self.assertEqual(self.client.get(self.link()).status_code, 400)

    def test_troca_de_senha_invalida_pedido_anterior(self):
        self.solicitar()
        self.usuario.set_password("OutraSenhaFicticia!71qT")
        self.usuario.save(update_fields=["password"])
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(self.link()).status_code, 400)

    def test_alteracao_administrativa_de_email_invalida_pedido(self):
        self.solicitar()
        Usuario.objects.filter(pk=self.usuario.pk).update(email="administrado@example.com")
        self.assertEqual(self.client.get(self.link()).status_code, 400)

    def test_outro_usuario_nao_abre_nem_confirma_o_link(self):
        self.solicitar()
        self.client.force_login(self.outro)
        response = self.client.get(self.link())
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "novo@example.com", status_code=400)
        self.assertEqual(self.client.post(reverse("contas:confirmar_email")).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")

    def test_link_adulterado_e_rejeitado(self):
        self.solicitar()
        token = self.token()
        alterado = ("A" if token[0] != "A" else "B") + token[1:]
        response = self.client.get(reverse("contas:confirmar_email_link", args=[alterado]))
        self.assertEqual(response.status_code, 400)

    def test_visitante_precisa_entrar_na_conta(self):
        self.solicitar()
        self.client.logout()
        for url in (reverse("contas:alterar_email"), self.link(), reverse("contas:confirmar_email")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_conta_bloqueada_nao_pode_confirmar(self):
        self.solicitar()
        Usuario.objects.filter(pk=self.usuario.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            confirmar_alteracao_email(usuario=self.usuario, token=self.token())
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")

    def test_email_ocupado_depois_da_solicitacao_impede_confirmacao(self):
        self.solicitar()
        self.abrir_confirmacao()
        Usuario.objects.filter(pk=self.outro.pk).update(email="novo@example.com")
        self.assertEqual(self.client.post(reverse("contas:confirmar_email")).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")

    def test_restricao_do_banco_trata_colisao_sem_erro_500(self):
        self.solicitar()
        self.abrir_confirmacao()
        # Simula uma validação desatualizada; a restrição real do PostgreSQL
        # continua impedindo que o endereço de outra conta seja utilizado.
        with patch("apps.contas.services.validar_novo_email", return_value=self.outro.email):
            response = self.client.post(reverse("contas:confirmar_email"))
        self.assertEqual(response.status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")
        self.assertTrue(AlteracaoEmail.objects.filter(usuario=self.usuario).exists())

    def test_id_forjado_na_solicitacao_nao_altera_a_conta_alheia(self):
        self.solicitar(usuario=self.outro.pk, pk=self.outro.pk)
        self.assertEqual(AlteracaoEmail.objects.get().usuario_id, self.usuario.pk)

    def test_falha_de_envio_preserva_solicitacao_anterior(self):
        self.solicitar()
        antes = list(AlteracaoEmail.objects.values())
        with patch("apps.contas.views.send_mail", side_effect=OSError("ERRO-PRIVADO")):
            response = self.solicitar("segundo@example.com")
        self.assertContains(response, "Não foi possível enviar a confirmação.")
        self.assertNotContains(response, "ERRO-PRIVADO")
        self.assertEqual(list(AlteracaoEmail.objects.values()), antes)

    def test_backend_sem_envio_nao_cria_confirmacao(self):
        with patch("apps.contas.views.send_mail", return_value=0):
            self.assertEqual(self.solicitar().status_code, 200)
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_senha_e_revalidada_no_banco_pelo_servico(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(password=make_password("Outra!senha72"))
        with self.assertRaises(ValidationError):
            solicitar_alteracao_email(
                usuario=self.usuario, novo_email="novo@example.com", senha_atual=self.senha,
            )
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_administradores_tambem_podem_alterar_o_proprio_email(self):
        for flag in ("is_staff", "is_superuser"):
            with self.subTest(flag=flag):
                admin = Usuario.objects.create_user(
                    f"email-{flag}", f"{flag}@example.com", self.senha, **{flag: True},
                )
                self.client.force_login(admin)
                self.assertEqual(self.solicitar(f"novo-{flag}@example.com").status_code, 302)
                self.abrir_confirmacao()
                self.assertEqual(self.client.post(reverse("contas:confirmar_email")).status_code, 302)
                admin.refresh_from_db()
                self.assertTrue(getattr(admin, flag))

    def test_protecoes_de_cache_e_referrer(self):
        self.solicitar()
        for url in (reverse("contas:alterar_email"), self.link(), reverse("contas:confirmar_email")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertEqual(response["Referrer-Policy"], "no-referrer")
                self.assertIn("Cookie", response["Vary"])

    def test_csrf_exigido_para_solicitar_e_confirmar(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.assertEqual(client.post(reverse("contas:alterar_email"), {}).status_code, 403)
        self.assertFalse(AlteracaoEmail.objects.exists())
        self.assertFalse(LimiteAcesso.objects.exists())
        client.get(reverse("contas:alterar_email"))
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(reverse("contas:alterar_email"), {
            "csrfmiddlewaretoken": token, "novo_email": "novo@example.com", "senha_atual": self.senha,
        }).status_code, 302)
        self.abrir_confirmacao(client)
        self.assertEqual(client.post(reverse("contas:confirmar_email"), {}).status_code, 403)
        self.assertEqual(client.post(reverse("contas:confirmar_email"), {
            "csrfmiddlewaretoken": token,
        }).status_code, 302)

    def test_origem_externa_e_rejeitada_mesmo_com_csrf_valido(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        client.get(reverse("contas:alterar_email"))
        response = client.post(reverse("contas:alterar_email"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "novo_email": "novo@example.com", "senha_atual": self.senha,
        }, HTTP_ORIGIN="https://intruso.example")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AlteracaoEmail.objects.exists())

    def test_confirmacao_rejeita_origem_externa(self):
        self.solicitar()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.abrir_confirmacao(client)
        response = client.post(reverse("contas:confirmar_email"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }, HTTP_ORIGIN="https://intruso.example")
        self.assertEqual(response.status_code, 403)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "atual@example.com")

    def test_limiter_tambem_restringe_varias_contas_no_mesmo_ip(self):
        for indice in range(6):
            usuario = Usuario.objects.create_user(
                f"limite-email-{indice}", f"atual-limite-{indice}@example.com", self.senha,
            )
            self.client.force_login(usuario)
            response = self.solicitar(f"novo-limite-{indice}@example.com")
            self.assertEqual(response.status_code, 302 if indice < 5 else 429)
        self.assertEqual(len(mail.outbox), 5)

    def test_limiter_por_conta_nao_e_contornado_por_email_ou_alias(self):
        for indice in range(3):
            self.assertEqual(self.solicitar(f"novo-{indice}@example.com").status_code, 302)
        antes = list(AlteracaoEmail.objects.values())
        response = self.client.post(reverse("contas_legacy:alterar_email"), {
            "novo_email": "quarto@example.com", "senha_atual": self.senha,
            "usuario": self.outro.pk,
        })
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(list(AlteracaoEmail.objects.values()), antes)


class ConcorrenciaAlteracaoEmailTests(TransactionTestCase):
    def setUp(self):
        self.senha = "SenhaFicticia!72rT9"
        self.usuarios = [Usuario.objects.create_user(
            f"email-concorrente-{indice}", f"atual-{indice}@example.com", self.senha,
        ) for indice in range(2)]

    def confirmar_em_paralelo(self, casos):
        barreira = Barrier(2)

        def confirmar(caso):
            close_old_connections()
            try:
                usuario, token = caso
                barreira.wait(timeout=15)
                try:
                    confirmar_alteracao_email(usuario=usuario, token=token)
                except ValidationError:
                    return "invalido"
                return "confirmado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(confirmar, casos))

    def test_duas_contas_nao_confirmam_o_mesmo_endereco(self):
        casos = []
        for usuario in self.usuarios:
            _, token = solicitar_alteracao_email(
                usuario=usuario, novo_email="disputado@example.com", senha_atual=self.senha,
            )
            casos.append((usuario, token))
        self.assertCountEqual(self.confirmar_em_paralelo(casos), ["confirmado", "invalido"])
        self.assertEqual(Usuario.objects.filter(email="disputado@example.com").count(), 1)
        self.assertEqual(Usuario.objects.count(), 2)
        self.assertEqual(AlteracaoEmail.objects.count(), 1)

    def test_confirmacoes_simultaneas_usam_token_somente_uma_vez(self):
        usuario = self.usuarios[0]
        _, token = solicitar_alteracao_email(
            usuario=usuario, novo_email="unico@example.com", senha_atual=self.senha,
        )
        casos = [(usuario, token), (usuario, token)]
        self.assertCountEqual(self.confirmar_em_paralelo(casos), ["confirmado", "invalido"])
        self.assertFalse(AlteracaoEmail.objects.exists())
