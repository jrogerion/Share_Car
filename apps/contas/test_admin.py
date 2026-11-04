from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse

from .models import Usuario


class UsuarioAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.senha = "Senha-teste!72rT9"
        cls.superusuario = Usuario.objects.create_superuser(
            "administrador", "admin@example.com", cls.senha,
        )
        cls.funcionario = Usuario.objects.create_user(
            "operador", "operador@example.com", cls.senha, is_staff=True,
        )
        cls.funcionario.user_permissions.set(Permission.objects.filter(
            content_type__app_label="contas", content_type__model="usuario",
        ))
        cls.usuario = Usuario.objects.create_user(
            "pessoa", "pessoa@example.com", cls.senha,
            first_name="Marina", last_name="Teste", locatario=True,
        )
        cls.grupo = Group.objects.create(name="Equipe de teste")

    def setUp(self):
        self.lista_url = reverse("admin:contas_usuario_changelist")
        self.adicionar_url = reverse("admin:contas_usuario_add")
        self.editar_url = reverse(
            "admin:contas_usuario_change", args=[self.usuario.pk],
        )

    def dados_edicao(self, usuario=None, **alteracoes):
        usuario = usuario or self.usuario
        return {
            "username": usuario.username, "email": usuario.email,
            "first_name": usuario.first_name, "last_name": usuario.last_name,
            "is_active": "on", "locatario": "on", **alteracoes,
        }

    def dados_criacao(self, **alteracoes):
        return {
            "username": "nova-pessoa", "email": "nova@example.com",
            "first_name": "Nova", "last_name": "Pessoa",
            "usable_password": "true", "password1": self.senha,
            "password2": self.senha, "locatario": "on", **alteracoes,
        }

    def test_visitante_e_usuario_comum_nao_acessam_admin(self):
        for usuario in (None, self.usuario):
            with self.subTest(usuario=usuario):
                if usuario:
                    self.client.force_login(usuario)
                response = self.client.get(self.lista_url)
                destino = f'{reverse("admin:login")}?next={self.lista_url}'
                self.assertRedirects(
                    response, destino,
                )

    def test_funcionario_sem_permissoes_recebe_403(self):
        self.funcionario.user_permissions.clear()
        self.client.force_login(self.funcionario)
        self.assertEqual(self.client.get(self.lista_url).status_code, 403)
        self.assertEqual(self.client.get(self.adicionar_url).status_code, 403)
        self.assertEqual(self.client.post(
            self.editar_url, self.dados_edicao(),
        ).status_code, 403)

    def test_permissao_de_consulta_nao_autoriza_edicao(self):
        self.funcionario.user_permissions.set(Permission.objects.filter(
            content_type__app_label="contas", codename="view_usuario",
        ))
        self.client.force_login(self.funcionario)
        self.assertEqual(self.client.get(self.editar_url).status_code, 200)
        self.assertEqual(self.client.post(
            self.editar_url, self.dados_edicao(first_name="Alterado"),
        ).status_code, 403)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Marina")

    def test_superusuario_pesquisa_e_filtra_contas(self):
        self.client.force_login(self.superusuario)
        for consulta in ("Marina", "Teste", "PESSOA@example.com"):
            with self.subTest(consulta=consulta):
                response = self.client.get(self.lista_url, {"q": consulta})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    list(response.context["cl"].queryset), [self.usuario],
                )
        response = self.client.get(self.lista_url, {"locatario__exact": "1"})
        self.assertEqual(list(response.context["cl"].queryset), [self.usuario])
        response = self.client.get(self.lista_url, {"is_active__exact": "0"})
        self.assertFalse(response.context["cl"].queryset.exists())
        response = self.client.get(self.lista_url, {
            "aprovacao_cnh__exact": "pendente",
        })
        self.assertEqual(response.context["cl"].queryset.count(), 3)

    def test_funcionario_so_lista_contas_comuns(self):
        self.client.force_login(self.funcionario)
        response = self.client.get(self.lista_url)
        self.assertEqual(list(response.context["cl"].queryset), [self.usuario])

    def test_formulario_nao_expoe_documentos_ou_cnh(self):
        self.client.force_login(self.superusuario)
        response = self.client.get(self.editar_url)
        self.assertEqual(response.status_code, 200)
        fields = response.context["adminform"].form.fields
        for campo in ("documento_identidade", "cnh_numero", "cnh_validade",
                      "aprovacao_documento", "aprovacao_cnh"):
            self.assertNotIn(campo, fields)
        self.assertContains(response, "Aprovações (somente consulta)")
        self.assertNotContains(response, self.senha)
        self.assertNotContains(response, self.usuario.password)

    def test_criacao_com_senha_protegida_e_email_normalizado(self):
        self.client.force_login(self.superusuario)
        response = self.client.post(self.adicionar_url, self.dados_criacao(
            email="  NOVA@EXAMPLE.COM  ", proprietario="on",
        ))
        self.assertEqual(response.status_code, 302)
        usuario = Usuario.objects.get(email="nova@example.com")
        self.assertTrue(usuario.check_password(self.senha))
        self.assertTrue(usuario.locatario)
        self.assertTrue(usuario.proprietario)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_criacao_exige_email_e_senha_valida(self):
        self.client.force_login(self.superusuario)
        for alteracoes, campo in (
            ({"email": ""}, "email"),
            ({"password1": "12345678", "password2": "12345678"}, "password2"),
            ({"password2": "outra-senha"}, "password2"),
        ):
            with self.subTest(campo=campo):
                response = self.client.post(
                    self.adicionar_url, self.dados_criacao(**alteracoes),
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["adminform"].form.errors)
        self.assertFalse(
            Usuario.objects.filter(username="nova-pessoa").exists(),
        )

    def test_email_duplicado_e_recusado_na_criacao_e_edicao(self):
        self.client.force_login(self.superusuario)
        for url, dados in (
            (self.adicionar_url, self.dados_criacao(
                email="PESSOA@EXAMPLE.COM",
            )),
            (self.editar_url, self.dados_edicao(email="ADMIN@EXAMPLE.COM")),
        ):
            with self.subTest(url=url):
                response = self.client.post(url, dados)
                self.assertEqual(response.status_code, 200)
                self.assertFormError(
                    response.context["adminform"].form, "email",
                    "Não é possível cadastrar este e-mail.",
                )
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "pessoa@example.com")

    def test_edicao_normaliza_email_da_propria_conta(self):
        self.client.force_login(self.funcionario)
        response = self.client.post(self.editar_url, self.dados_edicao(
            email="PESSOA@EXAMPLE.COM", first_name="Nome atualizado",
        ))
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "pessoa@example.com")
        self.assertEqual(self.usuario.first_name, "Nome atualizado")
        self.assertTrue(self.usuario.check_password(self.senha))

    def test_edicao_de_conta_legada_sem_email(self):
        self.usuario.email = ""
        self.usuario.save(update_fields=["email"])
        self.client.force_login(self.funcionario)
        response = self.client.post(self.editar_url, self.dados_edicao())
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "")

    def test_bloquear_e_desbloquear_conta(self):
        self.client.force_login(self.funcionario)
        response = self.client.post(
            self.editar_url, self.dados_edicao(is_active=""),
        )
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        response = self.client.post(self.editar_url, self.dados_edicao())
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_funcionario_nao_atribui_privilegios_por_post_forjado(self):
        self.client.force_login(self.funcionario)
        permissao = Permission.objects.get(
            content_type__app_label="contas", codename="change_usuario",
        )
        response = self.client.get(self.editar_url)
        fields = response.context["adminform"].form.fields
        for campo in (
            "is_staff", "is_superuser", "groups", "user_permissions",
        ):
            self.assertNotIn(campo, fields)
        response = self.client.post(self.editar_url, self.dados_edicao(
            is_staff="on", is_superuser="on", groups=[self.grupo.pk],
            user_permissions=[permissao.pk],
        ))
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)
        self.assertFalse(self.usuario.groups.exists())
        self.assertFalse(self.usuario.user_permissions.exists())

    def test_funcionario_nao_cria_conta_privilegiada(self):
        self.client.force_login(self.funcionario)
        response = self.client.post(self.adicionar_url, self.dados_criacao(
            is_staff="on", is_superuser="on", groups=[self.grupo.pk],
        ))
        self.assertEqual(response.status_code, 302)
        usuario = Usuario.objects.get(username="nova-pessoa")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.groups.exists())

    def test_funcionario_nao_altera_contas_privilegiadas(self):
        self.client.force_login(self.funcionario)
        for usuario in (self.funcionario, self.superusuario):
            for nome_url in (
                "contas_usuario_change", "auth_user_password_change",
            ):
                url = reverse(f"admin:{nome_url}", args=[usuario.pk])
                with self.subTest(usuario=usuario.pk, url=url):
                    response = self.client.get(url)
                    # A edição de objeto oculto pode redirecionar à listagem.
                    self.assertIn(response.status_code, (302, 403, 404))
                    response = self.client.post(url, self.dados_edicao(
                        usuario, is_superuser="on", password1="Outra-senha!39",
                        password2="Outra-senha!39", usable_password="true",
                    ))
                    self.assertIn(response.status_code, (302, 403, 404))
            usuario.refresh_from_db()
            self.assertTrue(usuario.check_password(self.senha))
        self.assertFalse(self.funcionario.is_superuser)

    def test_superusuario_pode_gerenciar_privilegios(self):
        self.client.force_login(self.superusuario)
        response = self.client.post(self.editar_url, self.dados_edicao(
            is_staff="on", groups=[self.grupo.pk],
        ))
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_staff)
        self.assertEqual(list(self.usuario.groups.all()), [self.grupo])

    def test_aprovacoes_nao_sao_alteradas_por_post(self):
        self.client.force_login(self.superusuario)
        response = self.client.post(self.editar_url, self.dados_edicao(
            aprovacao_documento="aprovado", aprovacao_cnh="aprovado",
        ))
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.aprovacao_documento, "pendente")
        self.assertEqual(self.usuario.aprovacao_cnh, "pendente")

    def test_troca_de_senha_nativa_para_conta_comum(self):
        self.client.force_login(self.funcionario)
        url = reverse(
            "admin:auth_user_password_change", args=[self.usuario.pk],
        )
        response = self.client.post(url, {
            "password1": "Nova-senha!97Xq", "password2": "Nova-senha!97Xq",
            "usable_password": "true",
        })
        self.assertRedirects(response, self.editar_url)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Nova-senha!97Xq"))
        self.assertFalse(self.usuario.check_password(self.senha))

    def test_troca_de_senha_exige_permissao_de_edicao(self):
        self.funcionario.user_permissions.clear()
        self.client.force_login(self.funcionario)
        url = reverse(
            "admin:auth_user_password_change", args=[self.usuario.pk],
        )
        response = self.client.post(url, {
            "password1": "Nova-senha!97Xq", "password2": "Nova-senha!97Xq",
            "usable_password": "true",
        })
        self.assertEqual(response.status_code, 403)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.senha))

    def test_exclusao_individual_e_em_massa_desabilitadas(self):
        for usuario in (self.funcionario, self.superusuario):
            with self.subTest(usuario=usuario.pk):
                self.client.force_login(usuario)
                url = reverse(
                    "admin:contas_usuario_delete", args=[self.usuario.pk],
                )
                response = self.client.post(url, {"post": "yes"})
                self.assertEqual(response.status_code, 403)
                response = self.client.get(self.lista_url)
                self.assertNotContains(response, 'value="delete_selected"')
                self.client.post(self.lista_url, {
                    "action": "delete_selected",
                    "_selected_action": [self.usuario.pk],
                    "post": "yes",
                })
                self.assertTrue(
                    Usuario.objects.filter(pk=self.usuario.pk).exists(),
                )

    def test_admin_exige_csrf_para_edicao(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superusuario)
        response = client.post(self.editar_url, self.dados_edicao())
        self.assertEqual(response.status_code, 403)
