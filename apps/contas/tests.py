from unittest.mock import patch

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
