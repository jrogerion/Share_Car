from unittest.mock import patch

from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .forms import CadastroUsuarioForm
from .models import Usuario
from .views import CadastroUsuarioView


class CadastroUsuarioTests(TestCase):
    def setUp(self):
        self.url = reverse("contas:cadastro")
        self.dados = {
            "first_name": "Pessoa", "last_name": "Teste",
            "email": "pessoa@example.com", "locatario": "on",
            "password1": "Senha-teste!72rT9", "password2": "Senha-teste!72rT9",
        }

    def test_formulario_acessivel_sem_aviso_de_previa(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'for="id_email"')
        self.assertContains(response, 'autocomplete="new-password"')
        self.assertNotContains(response, "Dados fictícios.")

    def test_cadastro_salva_senha_protegida_sem_autenticar(self):
        response = self.client.post(self.url, self.dados)
        self.assertRedirects(response, reverse("contas:cadastro_concluido"))
        usuario = Usuario.objects.get(email=self.dados["email"])
        self.assertTrue(usuario.check_password(self.dados["password1"]))
        self.assertNotEqual(usuario.password, self.dados["password1"])
        self.assertTrue(usuario.locatario)
        self.assertFalse(usuario.proprietario)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(usuario.aprovacao_documento, "pendente")
        self.assertEqual(usuario.aprovacao_cnh, "pendente")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_email_normalizado(self):
        self.dados["email"] = "  Pessoa@EXAMPLE.COM  "
        self.client.post(self.url, self.dados)
        self.assertTrue(Usuario.objects.filter(email="pessoa@example.com").exists())

    def test_email_duplicado_independente_de_caixa(self):
        Usuario.objects.create_user("legado", "PESSOA@example.com")
        response = self.client.post(self.url, self.dados)
        self.assertFormError(
            response.context["form"], "email",
            "Não é possível cadastrar este e-mail.",
        )
        self.assertEqual(Usuario.objects.count(), 1)

    def test_campos_obrigatorios_e_email_invalido(self):
        for campo in ("first_name", "last_name", "email", "password1", "password2"):
            with self.subTest(campo=campo):
                dados = {**self.dados, campo: ""}
                response = self.client.post(self.url, dados)
                self.assertIn(campo, response.context["form"].errors)
        response = self.client.post(self.url, {**self.dados, "email": "invalido"})
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(Usuario.objects.exists())

    def test_senha_fraca_e_confirmacao_diferente(self):
        for senha, confirmacao in (("12345678", "12345678"), ("Forte!73qP9", "outra")):
            with self.subTest(senha=senha):
                response = self.client.post(self.url, {
                    **self.dados, "password1": senha, "password2": confirmacao,
                })
                self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(Usuario.objects.exists())

    def test_perfis_independentes(self):
        for locatario, proprietario in ((True, False), (False, True), (True, True)):
            with self.subTest(locatario=locatario, proprietario=proprietario):
                dados = {
                    **self.dados,
                    "email": f"perfil-{int(locatario)}-{int(proprietario)}@example.com",
                    "locatario": "on" if locatario else "",
                    "proprietario": "on" if proprietario else "",
                }
                response = self.client.post(self.url, dados)
                self.assertRedirects(
                    response, reverse("contas:cadastro_concluido"),
                )
                usuario = Usuario.objects.get(email=dados["email"])
                self.assertEqual(usuario.locatario, locatario)
                self.assertEqual(usuario.proprietario, proprietario)

    def test_exige_ao_menos_um_perfil(self):
        response = self.client.post(self.url, {**self.dados, "locatario": ""})
        self.assertFormError(
            response.context["form"], None, "Selecione pelo menos um perfil de uso.",
        )
        self.assertFalse(Usuario.objects.exists())

    def test_campos_privilegiados_sao_ignorados(self):
        self.client.post(self.url, {
            **self.dados, "is_staff": "on", "is_superuser": "on",
            "is_active": "", "aprovacao_documento": "aprovado",
            "aprovacao_cnh": "aprovado", "username": "admin",
        })
        usuario = Usuario.objects.get()
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.is_active)
        self.assertEqual(usuario.aprovacao_documento, "pendente")
        self.assertEqual(usuario.aprovacao_cnh, "pendente")
        self.assertNotEqual(usuario.username, "admin")

    def test_post_sem_csrf_recusado(self):
        response = Client(enforce_csrf_checks=True).post(self.url, self.dados)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Usuario.objects.exists())

    def test_senha_nao_reaparece_em_formulario_invalido(self):
        response = self.client.post(self.url, {**self.dados, "email": ""})
        self.assertNotContains(response, self.dados["password1"])

    def test_banco_recusa_email_duplicado(self):
        Usuario.objects.create_user("primeiro", "PESSOA@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create_user("segundo", "pessoa@example.com")

    def test_contas_legadas_sem_email_preservadas(self):
        Usuario.objects.create_user("legado1")
        Usuario.objects.create_user("legado2")
        self.assertEqual(Usuario.objects.filter(email="").count(), 2)

    def test_email_duplicado_durante_gravacao(self):
        # Simula outra gravação após a validação, antes do INSERT deste form.
        form = CadastroUsuarioForm(self.dados)
        self.assertTrue(form.is_valid())
        Usuario.objects.create_user("concorrente", self.dados["email"])
        view = CadastroUsuarioView()
        with patch.object(view, "form_invalid", return_value="invalido"):
            self.assertEqual(view.form_valid(form), "invalido")
        self.assertIn("email", form.errors)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_erro_de_integridade_inesperado_nao_e_ocultado(self):
        form = CadastroUsuarioForm(self.dados)
        self.assertTrue(form.is_valid())
        with patch.object(form, "save", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                CadastroUsuarioView().form_valid(form)


class AutenticacaoUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.senha = "Senha-teste!72rT9"
        cls.usuario = Usuario.objects.create_user(
            username="usuario-interno", email="pessoa@example.com",
            password=cls.senha, first_name="Pessoa", locatario=True,
        )

    def setUp(self):
        self.url = reverse("core:entrar")
        self.dados = {"username": self.usuario.email, "password": self.senha}

    def test_formulario_de_login_funcional(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'type="email"')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, "Dados fictícios.")

    def test_login_por_email_e_sessao_persistente(self):
        response = self.client.post(self.url, self.dados)
        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)
        response = self.client.get(self.url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "Sua sessão está ativa.")
        self.assertContains(response, f'action="{reverse("contas:sair")}"')
        self.usuario.refresh_from_db()
        self.assertIsNotNone(self.usuario.last_login)

    def test_email_ignora_caixa_e_espacos_externos(self):
        response = self.client.post(self.url, {
            **self.dados, "username": "  PESSOA@EXAMPLE.COM  ",
        })
        self.assertRedirects(response, reverse("core:home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_mesmo_erro_para_senha_incorreta_email_inexistente_e_inativo(self):
        for ativo, dados in (
            (True, {**self.dados, "password": "incorreta"}),
            (True, {**self.dados, "username": "inexistente@example.com"}),
            (False, self.dados),
        ):
            with self.subTest(ativo=ativo, email=dados["username"]):
                self.usuario.is_active = ativo
                self.usuario.save(update_fields=["is_active"])
                response = self.client.post(self.url, dados)
                self.assertFormError(
                    response.context["form"], None, "E-mail ou senha inválidos.",
                )
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_campos_invalidos_nao_autenticam(self):
        for dados in ({}, {**self.dados, "username": "invalido"},
                      {**self.dados, "password": ""}):
            with self.subTest(dados=dados.keys()):
                response = self.client.post(self.url, dados)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_site_nao_aceita_username_como_alternativa_ao_email(self):
        Usuario.objects.create_user(
            username="outro@example.com", email="diferente@example.com",
            password=self.senha,
        )
        response = self.client.post(self.url, {
            **self.dados, "username": "outro@example.com",
        })
        self.assertFormError(
            response.context["form"], None, "E-mail ou senha inválidos.",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_preserva_senha_sem_remover_espacos(self):
        senha = "  Senha-espacos!93  "
        self.usuario.set_password(senha)
        self.usuario.save(update_fields=["password"])
        response = self.client.post(self.url, {**self.dados, "password": senha})
        self.assertRedirects(response, reverse("core:home"))

    def test_redirecionamento_interno_apos_login(self):
        destino = reverse("core:reservas")
        response = self.client.post(self.url, {**self.dados, "next": destino})
        self.assertRedirects(response, destino)

    def test_redirecionamentos_externos_recusados(self):
        for destino in ("https://externo.example/", "//externo.example/"):
            with self.subTest(destino=destino):
                self.client.logout()
                response = self.client.post(self.url, {
                    **self.dados, "next": destino,
                })
                self.assertRedirects(response, reverse("core:home"))

    def test_next_preservado_apos_erro_sem_executar_html(self):
        destino = '"><script>alert(1)</script>'
        response = self.client.post(self.url, {
            **self.dados, "password": "incorreta", "next": destino,
        })
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, self.senha)
        self.assertContains(response, "&lt;script&gt;")

    def test_sair_por_post_encerra_sessao(self):
        self.client.post(self.url, self.dados)
        response = self.client.post(reverse("contas:sair"))
        self.assertRedirects(response, self.url)
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.get(self.url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_get_nao_encerra_sessao(self):
        self.client.post(self.url, self.dados)
        response = self.client.get(reverse("contas:sair"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_recusa_redirecionamento_externo(self):
        self.client.post(self.url, self.dados)
        response = self.client.post(reverse("contas:sair"), {
            "next": "https://externo.example/",
        })
        self.assertRedirects(response, self.url)

    def test_login_e_logout_exigem_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, self.dados).status_code, 403)
        client.get(self.url)
        response = client.post(self.url, {
            **self.dados, "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.post(reverse("contas:sair")).status_code, 403)
        self.assertIn("_auth_user_id", client.session)
        response = client.post(reverse("contas:sair"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", client.session)

    def test_login_rotaciona_identificador_de_sessao(self):
        session = self.client.session
        session["teste"] = "sessao-anonima"
        session.save()
        chave_anterior = session.session_key
        self.client.post(self.url, self.dados)
        self.assertNotEqual(self.client.session.session_key, chave_anterior)

    def test_usuario_bloqueado_perde_acesso_na_proxima_requisicao(self):
        self.client.post(self.url, self.dados)
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        response = self.client.get(self.url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_admin_preserva_login_por_username(self):
        self.usuario.is_staff = True
        self.usuario.save(update_fields=["is_staff"])
        response = self.client.post(reverse("admin:login"), {
            "username": self.usuario.username, "password": self.senha,
            "next": reverse("admin:index"),
        })
        self.assertRedirects(response, reverse("admin:index"))

    def test_backend_recusa_email_vazio_e_senha_ausente(self):
        self.assertIsNone(authenticate(email="", password=self.senha))
        self.assertIsNone(authenticate(email=self.usuario.email))

    def test_cadastro_seguido_de_login(self):
        response = self.client.post(reverse("contas:cadastro"), {
            "first_name": "Nova", "last_name": "Pessoa",
            "email": "nova@example.com", "proprietario": "on",
            "password1": self.senha, "password2": self.senha,
        })
        self.assertRedirects(response, reverse("contas:cadastro_concluido"))
        response = self.client.post(self.url, {
            "username": "nova@example.com", "password": self.senha,
        })
        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            Usuario.objects.get(email="nova@example.com").pk,
        )
