from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from http.client import HTTPConnection
from threading import Barrier, Thread
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler, make_server

from django.core import mail
from django.core.handlers.wsgi import WSGIRequest
from django.db import close_old_connections, connections
from django.test import (
    Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings,
)
from django.urls import reverse
from django.utils import timezone

from .limites import consumir_tentativa, ip_da_conexao
from .models import LimiteAcesso, Usuario


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LimitesAcessoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.senha = "SenhaFicticia!72rT9"
        cls.usuario = Usuario.objects.create_user(
            "limite-ficticio", "limite@example.com", cls.senha,
        )

    def login(self, email="limite@example.com", senha="incorreta", **headers):
        return self.client.post(reverse("core:entrar"), {
            "username": email, "password": senha,
        }, **headers)

    def test_login_limita_par_entre_clientes_e_libera_apos_expiracao(self):
        agora = timezone.now()
        with patch("apps.contas.limites.timezone.now", return_value=agora):
            for _ in range(5):
                self.assertEqual(self.login().status_code, 200)
            outro_client = Client()
            response = outro_client.post(reverse("core:entrar"), {
                "username": " LIMITE@EXAMPLE.COM ", "password": self.senha,
            })
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response["Retry-After"], "300")
            self.assertIn("no-store", response["Cache-Control"])
            self.assertNotIn("_auth_user_id", outro_client.session)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        with patch("apps.contas.limites.timezone.now", return_value=agora + timedelta(minutes=5)):
            self.assertEqual(self.login(senha=self.senha).status_code, 302)
            self.assertEqual(self.client.session["_auth_user_id"], str(self.usuario.pk))

    def test_bloqueio_nao_estende_janela(self):
        agora = timezone.now()
        with patch("apps.contas.limites.timezone.now", return_value=agora):
            for _ in range(5):
                self.login()
        antes = list(LimiteAcesso.objects.order_by("pk").values())
        with patch("apps.contas.limites.timezone.now", return_value=agora + timedelta(seconds=30)):
            response = self.login()
        self.assertEqual(response["Retry-After"], "270")
        self.assertEqual(list(LimiteAcesso.objects.order_by("pk").values()), antes)

    def test_variar_email_nao_contorna_limite_por_ip(self):
        for indice in range(20):
            self.assertEqual(self.login(f"inexistente-{indice}@example.com").status_code, 200)
        total = LimiteAcesso.objects.count()
        self.assertEqual(self.login("novo@example.com").status_code, 429)
        self.assertEqual(LimiteAcesso.objects.count(), total)

    def test_ip_diferente_nao_bloqueia_conta_globalmente(self):
        for _ in range(5):
            self.login()
        self.assertEqual(self.login().status_code, 429)
        self.assertEqual(self.login(senha=self.senha, REMOTE_ADDR="192.0.2.8").status_code, 302)

    def test_headers_forjados_nao_trocam_ip(self):
        for _ in range(5):
            self.login()
        self.assertEqual(self.login(
            HTTP_X_FORWARDED_FOR="192.0.2.99", HTTP_X_REAL_IP="192.0.2.100",
            HTTP_FORWARDED="for=192.0.2.101",
            HTTP_CF_CONNECTING_IP="192.0.2.102",
        ).status_code, 429)

    def test_clientes_atras_do_mesmo_proxy_compartilham_limite(self):
        url = reverse("contas:recuperar_senha")
        # Simula um proxy sem restauração confiável do IP: muda só o header.
        for indice in range(5):
            response = self.client.post(
                url, {"email": f"inexistente-{indice}@example.com"},
                REMOTE_ADDR="192.0.2.10",
                HTTP_CF_CONNECTING_IP=f"192.0.2.{indice + 20}",
            )
            self.assertEqual(response.status_code, 302)
        response = self.client.post(
            url, {"email": "outro@example.com"}, REMOTE_ADDR="192.0.2.10",
            HTTP_CF_CONNECTING_IP="192.0.2.99",
        )
        self.assertEqual(response.status_code, 429)
        # Outra conexão real não herda o bloqueio, ainda que repita o header.
        response = self.client.post(
            url, {"email": "outro@example.com"}, REMOTE_ADDR="192.0.2.11",
            HTTP_CF_CONNECTING_IP="192.0.2.99",
        )
        self.assertEqual(response.status_code, 302)

    def test_recuperacao_compartilha_limite_com_alias_sem_enviar_mais_emails(self):
        for _ in range(3):
            response = self.client.post(reverse("contas:recuperar_senha"), {
                "email": self.usuario.email,
            })
            self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 3)
        for nome in ("contas:recuperar_senha", "contas_legacy:recuperar_senha"):
            response = self.client.post(reverse(nome), {"email": self.usuario.email})
            self.assertEqual(response.status_code, 429)
            self.assertLessEqual(int(response["Retry-After"]), 900)
        self.assertEqual(len(mail.outbox), 3)

    def test_recuperacao_tem_limite_total_por_ip(self):
        for indice in range(5):
            self.assertEqual(self.client.post(reverse("contas:recuperar_senha"), {
                "email": f"ausente-{indice}@example.com",
            }).status_code, 302)
        self.assertEqual(self.client.post(reverse("contas:recuperar_senha"), {
            "email": "outro@example.com",
        }).status_code, 429)

    def test_recuperacao_volta_a_enviar_apos_expiracao(self):
        agora = timezone.now()
        url = reverse("contas:recuperar_senha")
        with patch("apps.contas.limites.timezone.now", return_value=agora):
            for _ in range(3):
                self.client.post(url, {"email": self.usuario.email})
            self.assertEqual(self.client.post(url, {"email": self.usuario.email}).status_code, 429)
        with patch("apps.contas.limites.timezone.now", return_value=agora + timedelta(minutes=15)):
            self.assertEqual(self.client.post(url, {"email": self.usuario.email}).status_code, 302)
        self.assertEqual(len(mail.outbox), 4)

    def test_conta_existente_e_inexistente_tem_mesmo_limite_e_resposta(self):
        for email, ip in ((self.usuario.email, "192.0.2.1"), ("ausente@example.com", "192.0.2.2")):
            with self.subTest(email=email):
                for _ in range(3):
                    response = self.client.post(reverse("contas:recuperar_senha"), {
                        "email": email,
                    }, REMOTE_ADDR=ip)
                    self.assertRedirects(response, reverse("contas:recuperar_senha_enviado"))
                response = self.client.post(reverse("contas:recuperar_senha"), {
                    "email": email,
                }, REMOTE_ADDR=ip)
                self.assertEqual(response.status_code, 429)
                self.assertNotContains(response, email, status_code=429)

    def test_admin_compartilha_limite_de_login(self):
        for _ in range(5):
            self.login()
        response = self.client.post(reverse("admin:login"), {
            "username": self.usuario.email, "password": self.senha,
        })
        self.assertEqual(response.status_code, 429)

    def test_get_e_csrf_invalido_nao_consumem_tentativas(self):
        client = Client(enforce_csrf_checks=True)
        for nome in ("core:entrar", "admin:login", "contas:recuperar_senha"):
            self.assertEqual(client.get(reverse(nome)).status_code, 200)
            self.assertEqual(client.post(reverse(nome), {}).status_code, 403)
        self.assertFalse(LimiteAcesso.objects.exists())

    def test_post_com_csrf_valido_tambem_e_limitado(self):
        client = Client(enforce_csrf_checks=True)
        url = reverse("core:entrar")
        client.get(url)
        payload = {
            "username": self.usuario.email, "password": "incorreta",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }
        for _ in range(5):
            self.assertEqual(client.post(url, payload).status_code, 200)
        self.assertEqual(client.post(url, payload).status_code, 429)

    def test_formulario_invalido_conta_e_acoes_sao_independentes(self):
        for _ in range(5):
            self.assertEqual(self.client.post(reverse("core:entrar"), {}).status_code, 200)
        self.assertEqual(self.client.post(reverse("core:entrar"), {}).status_code, 429)
        self.assertEqual(self.client.post(reverse("contas:recuperar_senha"), {}).status_code, 200)

    def test_chaves_nao_contem_ip_email_ou_senha(self):
        self.login()
        for chave in LimiteAcesso.objects.values_list("chave", flat=True):
            self.assertRegex(chave, r"^[0-9a-f]{64}$")
            self.assertNotIn(self.usuario.email, chave)
            self.assertNotIn("127.0.0.1", chave)

    def test_ipv6_normalizado_e_ip_ausente(self):
        request = type("Request", (), {"META": {"REMOTE_ADDR": "2001:db8:0:0:0:0:0:1"}})()
        self.assertEqual(ip_da_conexao(request), "2001:db8::1")
        request.META = {}
        self.assertEqual(ip_da_conexao(request), "desconhecido")


class IPConexaoHTTPTests(SimpleTestCase):
    """Sockets reais, sem banco ou endpoint de diagnóstico no site."""

    def setUp(self):
        class SemLogs(WSGIRequestHandler):
            def log_message(self, *args):
                pass

        def application(environ, start_response):
            ip = ip_da_conexao(WSGIRequest(environ)).encode("ascii")
            start_response("200 OK", [
                ("Content-Type", "text/plain"), ("Content-Length", str(len(ip))),
            ])
            return [ip]

        self.server = make_server(
            "127.0.0.1", 0, application, handler_class=SemLogs,
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.encerrar)

    def encerrar(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def consultar(self, origem="127.0.0.1", headers=None):
        connection = HTTPConnection(
            "127.0.0.1", self.server.server_port,
            source_address=(origem, 0), timeout=5,
        )
        try:
            connection.request("GET", "/", headers=headers or {})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            return response.read().decode("ascii")
        finally:
            connection.close()

    def test_socket_real_prevalece_sobre_cabecalhos(self):
        self.assertEqual(self.consultar(headers={
            "X-Forwarded-For": "192.0.2.1, 192.0.2.2",
            "X-Real-IP": "192.0.2.3",
            "Forwarded": "for=192.0.2.4",
            "CF-Connecting-IP": "192.0.2.5",
        }), "127.0.0.1")

    def test_origens_distintas_sem_nat_permanecem_distintas(self):
        self.assertEqual(self.consultar(origem="127.0.0.1"), "127.0.0.1")
        self.assertEqual(self.consultar(origem="127.0.0.2"), "127.0.0.2")


class ConcorrenciaLimitesTests(TransactionTestCase):
    def test_ips_com_varios_identificadores_respeitam_limite_total(self):
        barreira = Barrier(8)

        def tentar(indice):
            close_old_connections()
            try:
                barreira.wait(timeout=15)
                return consumir_tentativa("recuperacao", "192.0.2.21", f"teste-{indice}@example.com")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as executor:
            resultados = list(executor.map(tentar, range(8)))
        self.assertEqual(resultados.count(0), 5)
        self.assertEqual(sum(espera > 0 for espera in resultados), 3)
        self.assertEqual(LimiteAcesso.objects.count(), 6)

    def test_conexoes_concorrentes_nao_perdem_incrementos(self):
        barreira = Barrier(8)

        def tentar(_):
            close_old_connections()
            try:
                barreira.wait(timeout=15)
                return consumir_tentativa("login", "192.0.2.20", "teste@example.com")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as executor:
            resultados = list(executor.map(tentar, range(8)))
        self.assertEqual(resultados.count(0), 5)
        self.assertEqual(sum(espera > 0 for espera in resultados), 3)
        self.assertEqual(list(LimiteAcesso.objects.values_list("tentativas", flat=True)), [5, 5])
