from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import PerfilUsuarioForm
from .models import Usuario


class PerfilUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.validade = timezone.localdate() + timedelta(days=365)
        cls.usuario = Usuario.objects.create_user(
            "pessoa", "pessoa@example.com", "Senha-teste!72rT9",
            first_name="Pessoa", last_name="Teste", locatario=True,
            cnh_numero="CNH-TESTE-001", cnh_validade=cls.validade,
            aprovacao_cnh=Usuario.Aprovacao.APROVADO,
            aprovacao_documento=Usuario.Aprovacao.APROVADO,
        )
        cls.outro = Usuario.objects.create_user(
            "outra", "outra@example.com", "Outra-senha!93",
            first_name="Outra pessoa", cnh_numero="CNH-TESTE-002",
        )

    def setUp(self):
        self.url = reverse("contas:perfil")
        self.client.force_login(self.usuario)
        self.dados = {
            "first_name": "Pessoa", "last_name": "Teste", "locatario": "on",
            "cnh_numero": self.usuario.cnh_numero,
            "cnh_validade": self.validade.isoformat(),
        }

    def test_visitante_precisa_autenticar_para_consultar_e_salvar(self):
        self.client.logout()
        for method in (self.client.get, self.client.post):
            response = method(self.url, self.dados)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("core:entrar")))
            self.assertIn("next=", response.url)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Pessoa")

    def test_formulario_exibe_apenas_dados_proprios_e_aprovacoes(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.usuario.email)
        self.assertContains(response, self.usuario.cnh_numero)
        self.assertContains(response, 'type="date"')
        self.assertContains(response, f'value="{self.validade.isoformat()}"')
        self.assertContains(response, 'for="id_cnh_numero"')
        self.assertContains(response, "Aprovado")
        self.assertNotContains(response, self.outro.email)
        self.assertNotContains(response, self.outro.cnh_numero)
        self.assertNotContains(response, "Dados fictícios.")
        fields = response.context["form"].fields
        self.assertEqual(set(fields), set(PerfilUsuarioForm.Meta.fields))
        self.assertNotIn("email", fields)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_atualiza_nome_e_perfis_com_mensagem_de_sucesso(self):
        response = self.client.post(self.url, {
            **self.dados, "first_name": "Nome novo", "proprietario": "on",
        }, follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, "Perfil atualizado com sucesso.")
        self.assertContains(response, ">Nome novo</span>", count=2)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nome novo")
        self.assertTrue(self.usuario.locatario)
        self.assertTrue(self.usuario.proprietario)
        self.assertNotContains(
            self.client.get(self.url), "Perfil atualizado com sucesso.",
        )

    def test_perfis_podem_ser_independentes(self):
        for locatario, proprietario in (
            (True, False), (False, True), (True, True),
        ):
            with self.subTest(locatario=locatario, proprietario=proprietario):
                response = self.client.post(self.url, {
                    **self.dados, "locatario": "on" if locatario else "",
                    "proprietario": "on" if proprietario else "",
                })
                self.assertRedirects(response, self.url)
                self.usuario.refresh_from_db()
                self.assertEqual(self.usuario.locatario, locatario)
                self.assertEqual(self.usuario.proprietario, proprietario)

    def test_campos_invalidos_nao_gravam_alteracoes(self):
        casos = (
            ({"first_name": ""}, "first_name"),
            ({"last_name": ""}, "last_name"),
            ({"locatario": ""}, "__all__"),
            ({"cnh_validade": "data-invalida"}, "cnh_validade"),
            ({"cnh_validade": "2026-02-30"}, "cnh_validade"),
            ({"cnh_numero": "X" * 21}, "cnh_numero"),
            ({"cnh_numero": ""}, "cnh_numero"),
            ({"cnh_validade": ""}, "cnh_validade"),
        )
        for alteracoes, campo in casos:
            with self.subTest(campo=campo, alteracoes=alteracoes):
                response = self.client.post(self.url, {
                    **self.dados, "last_name": "Alterado", **alteracoes,
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
                self.assertNotContains(
                    response, "Perfil atualizado com sucesso.",
                )
                self.usuario.refresh_from_db()
                self.assertEqual(self.usuario.last_name, "Teste")
                self.assertEqual(self.usuario.cnh_numero, "CNH-TESTE-001")
                self.assertEqual(self.usuario.aprovacao_cnh, "aprovado")

    def test_pode_manter_cnh_nao_informada(self):
        response = self.client.post(self.url, {
            **self.dados, "cnh_numero": "", "cnh_validade": "",
        })
        self.assertRedirects(response, self.url)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.cnh_numero, "")
        self.assertIsNone(self.usuario.cnh_validade)
        self.assertEqual(self.usuario.aprovacao_cnh, "pendente")

    def test_alterar_numero_ou_validade_reinicia_aprovacao(self):
        for alteracoes in (
            {"cnh_numero": "CNH-TESTE-003"},
            {"cnh_validade": (self.validade + timedelta(days=1)).isoformat()},
        ):
            with self.subTest(alteracoes=alteracoes):
                Usuario.objects.filter(pk=self.usuario.pk).update(
                    cnh_numero=self.dados["cnh_numero"],
                    cnh_validade=self.validade, aprovacao_cnh="aprovado",
                )
                response = self.client.post(self.url, {
                    **self.dados, **alteracoes,
                })
                self.assertRedirects(response, self.url)
                self.usuario.refresh_from_db()
                self.assertEqual(self.usuario.aprovacao_cnh, "pendente")
                self.assertEqual(self.usuario.aprovacao_documento, "aprovado")

    def test_cnh_inalterada_preserva_aprovacao(self):
        for aprovacao in Usuario.Aprovacao.values:
            with self.subTest(aprovacao=aprovacao):
                Usuario.objects.filter(pk=self.usuario.pk).update(
                    aprovacao_cnh=aprovacao,
                )
                self.client.post(self.url, {
                    **self.dados, "last_name": "Sobrenome atualizado",
                })
                self.usuario.refresh_from_db()
                self.assertEqual(self.usuario.aprovacao_cnh, aprovacao)

    def test_cnh_vencida_pode_ser_salva_com_aviso(self):
        ontem = timezone.localdate() - timedelta(days=1)
        response = self.client.post(self.url, {
            **self.dados, "cnh_validade": ontem.isoformat(),
        }, follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, "Sua CNH está vencida.")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.cnh_validade, ontem)
        self.assertEqual(self.usuario.aprovacao_cnh, "pendente")

    def test_cnh_com_validade_hoje_ainda_nao_esta_vencida(self):
        response = self.client.post(self.url, {
            **self.dados, "cnh_validade": timezone.localdate().isoformat(),
        }, follow=True)
        self.assertNotContains(response, "Sua CNH está vencida.")

    def test_campos_protegidos_e_identificadores_enviados_sao_ignorados(self):
        response = self.client.post(f"{self.url}?pk={self.outro.pk}", {
            **self.dados, "id": self.outro.pk, "pk": self.outro.pk,
            "user_id": self.outro.pk, "username": "administrador",
            "email": "alterado@example.com", "password": "outra-senha",
            "is_staff": "on", "is_superuser": "on", "is_active": "",
            "aprovacao_cnh": "rejeitado", "aprovacao_documento": "rejeitado",
            "first_name": "Nome novo",
        })
        self.assertRedirects(response, self.url)
        self.usuario.refresh_from_db()
        self.outro.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nome novo")
        self.assertEqual(self.usuario.email, "pessoa@example.com")
        self.assertEqual(self.usuario.username, "pessoa")
        self.assertTrue(self.usuario.check_password("Senha-teste!72rT9"))
        self.assertFalse(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)
        self.assertTrue(self.usuario.is_active)
        self.assertEqual(self.usuario.aprovacao_cnh, "aprovado")
        self.assertEqual(self.usuario.aprovacao_documento, "aprovado")
        self.assertEqual(self.outro.first_name, "Outra pessoa")
        self.assertEqual(self.outro.cnh_numero, "CNH-TESTE-002")

    def test_consulta_ignora_identificador_de_outro_usuario(self):
        response = self.client.get(self.url, {"pk": self.outro.pk})
        self.assertEqual(response.context["object"].pk, self.usuario.pk)
        self.assertNotContains(response, self.outro.cnh_numero)

    def test_csrf_obrigatorio_para_salvar(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.assertEqual(client.post(self.url, self.dados).status_code, 403)
        client.get(self.url)
        response = client.post(self.url, {
            **self.dados,
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, self.url)

    def test_formulario_commit_false_nao_grava(self):
        form = PerfilUsuarioForm(
            {**self.dados, "cnh_numero": "CNH-TESTE-003"},
            instance=self.usuario,
        )
        self.assertTrue(form.is_valid())
        usuario = form.save(commit=False)
        self.assertEqual(usuario.aprovacao_cnh, "pendente")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.cnh_numero, "CNH-TESTE-001")
        self.assertEqual(self.usuario.aprovacao_cnh, "aprovado")

    def test_salvamento_nao_sobrescreve_campos_alterados_fora_do_perfil(self):
        form = PerfilUsuarioForm(self.dados, instance=self.usuario)
        self.assertTrue(form.is_valid())
        Usuario.objects.filter(pk=self.usuario.pk).update(
            email="novo@example.com", is_active=False,
            aprovacao_cnh="rejeitado",
        )
        form.save()
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "novo@example.com")
        self.assertFalse(self.usuario.is_active)
        self.assertEqual(self.usuario.aprovacao_cnh, "rejeitado")

    def test_menu_destaca_minha_conta(self):
        response = self.client.get(self.url)
        self.assertContains(
            response, 'aria-label="Minha conta: Pessoa" aria-current="page"',
            count=2,
        )
