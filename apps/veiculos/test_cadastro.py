from django.test import Client, TestCase
from django.urls import reverse

from apps.contas.models import Usuario

from .forms import CadastroVeiculoForm
from .models import Veiculo


class CadastroVeiculoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.proprietario = Usuario.objects.create_user(
            "proprietario", "proprietario@example.com", "Senha-teste!72rT9",
            proprietario=True, aprovacao_documento="aprovado",
        )
        cls.outro = Usuario.objects.create_user(
            "outro", "outro@example.com", proprietario=True,
            aprovacao_documento="aprovado",
        )

    def setUp(self):
        self.url = reverse("core:veiculo")
        self.lista_url = reverse("veiculos:meus")
        self.client.force_login(self.proprietario)
        self.dados = {
            "caracteristicas": "Carro fictício de teste, manual e conservado.",
            "cidade": "São Paulo", "categoria": "Hatch", "cambio": "Manual",
            "combustivel": "Flex", "passageiros": "5",
            "preco_diaria": "150.00",
        }

    def criar_veiculo(self, **dados):
        return Veiculo.objects.create(
            **{**self.dados, "proprietario": self.proprietario, **dados},
        )

    def test_visitante_precisa_login_para_cadastrar_e_listar(self):
        self.client.logout()
        for url in (self.url, self.lista_url):
            response = self.client.get(url)
            self.assertRedirects(
                response, f'{reverse("core:entrar")}?next={url}',
            )
        self.assertEqual(
            self.client.post(self.url, self.dados).status_code, 302,
        )
        self.assertFalse(Veiculo.objects.exists())

    def test_formulario_funcional_sem_campos_administrativos(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'for="id_caracteristicas"')
        self.assertNotContains(response, "Dados fictícios.")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            set(response.context["form"].fields),
            set(CadastroVeiculoForm.Meta.fields),
        )
        for campo in ("proprietario", "aprovacao", "bloqueado", "ativo"):
            self.assertNotContains(response, f'name="{campo}"')

    def test_cadastro_vincula_dono_e_aguarda_aprovacao(self):
        response = self.client.post(self.url, self.dados, follow=True)
        self.assertRedirects(response, self.lista_url)
        self.assertContains(
            response, "Veículo cadastrado e enviado para análise.",
        )
        self.assertContains(response, "Pendente")
        veiculo = Veiculo.objects.get()
        self.assertEqual(veiculo.proprietario_id, self.proprietario.pk)
        self.assertEqual(veiculo.aprovacao, "pendente")
        self.assertTrue(veiculo.ativo)
        self.assertFalse(veiculo.bloqueado)
        self.assertEqual(veiculo.passageiros, 5)
        self.assertEqual(str(veiculo.preco_diaria), "150.00")
        # A CNH não é requisito para anunciar, somente a identidade aprovada.
        self.assertFalse(self.proprietario.cnh_numero)

    def test_cadastro_nao_aparece_na_api_ou_busca_publica(self):
        self.client.post(self.url, self.dados)
        response = self.client.get(reverse("veiculos_api:lista"))
        self.assertEqual(response.json()["count"], 0)
        response = self.client.get(reverse("core:resultados"))
        self.assertNotContains(response, self.dados["caracteristicas"])
        veiculo = Veiculo.objects.get()
        response = self.client.get(reverse("core:detalhes", args=[veiculo.pk]))
        self.assertEqual(response.status_code, 404)

    def test_sem_perfil_ou_identidade_aprovada_nao_pode_cadastrar(self):
        for proprietario, aprovacao in (
            (False, "aprovado"), (True, "pendente"), (True, "rejeitado"),
        ):
            with self.subTest(proprietario=proprietario, aprovacao=aprovacao):
                Usuario.objects.filter(pk=self.proprietario.pk).update(
                    proprietario=proprietario, aprovacao_documento=aprovacao,
                )
                for method in (self.client.get, self.client.post):
                    response = method(self.url, self.dados)
                    self.assertRedirects(response, reverse("contas:perfil"))
                self.assertFalse(Veiculo.objects.exists())

    def test_reativacao_ou_aprovacao_falsa_no_post_nao_burla_permissao(self):
        Usuario.objects.filter(pk=self.proprietario.pk).update(
            aprovacao_documento="pendente",
        )
        response = self.client.post(self.url, {
            **self.dados, "aprovacao_documento": "aprovado",
            "proprietario": self.outro.pk,
        })
        self.assertRedirects(response, reverse("contas:perfil"))
        self.assertFalse(Veiculo.objects.exists())

    def test_conta_inativa_nao_cadastra(self):
        Usuario.objects.filter(pk=self.proprietario.pk).update(is_active=False)
        response = self.client.post(self.url, self.dados)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("core:entrar")))
        self.assertFalse(Veiculo.objects.exists())

    def test_post_nao_escolhe_dono_aprovacao_ou_bloqueio(self):
        response = self.client.post(self.url, {
            **self.dados, "proprietario": self.outro.pk,
            "proprietario_id": self.outro.pk, "aprovacao": "aprovado",
            "ativo": "", "bloqueado": "on",
        })
        self.assertRedirects(response, self.lista_url)
        veiculo = Veiculo.objects.get()
        self.assertEqual(veiculo.proprietario_id, self.proprietario.pk)
        self.assertEqual(veiculo.aprovacao, "pendente")
        self.assertFalse(veiculo.bloqueado)
        self.assertTrue(veiculo.ativo)

    def test_campos_obrigatorios(self):
        for campo in CadastroVeiculoForm.Meta.fields:
            with self.subTest(campo=campo):
                response = self.client.post(self.url, {
                    **self.dados, campo: "",
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
        self.assertFalse(Veiculo.objects.exists())

    def test_valores_invalidos_nao_criam_veiculo(self):
        casos = (
            ("preco_diaria", "0"), ("preco_diaria", "-1"),
            ("preco_diaria", "1.001"), ("preco_diaria", "100000000.00"),
            ("passageiros", "0"), ("passageiros", "-1"),
            ("passageiros", "1.5"), ("passageiros", "32768"),
            ("cidade", " " * 3), ("cidade", "X" * 151),
            ("categoria", "X" * 51), ("cambio", "X" * 51),
            ("combustivel", "X" * 51),
        )
        for campo, valor in casos:
            with self.subTest(campo=campo, valor=valor):
                response = self.client.post(self.url, {
                    **self.dados, campo: valor,
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
        self.assertFalse(Veiculo.objects.exists())

    def test_csrf_obrigatorio(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.proprietario)
        self.assertEqual(client.post(self.url, self.dados).status_code, 403)
        self.assertFalse(Veiculo.objects.exists())
        client.get(self.url)
        response = client.post(self.url, {
            **self.dados,
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, self.lista_url)
        self.assertEqual(Veiculo.objects.count(), 1)

    def test_lista_apenas_veiculos_do_usuario_inclusive_nao_publicos(self):
        proprio = self.criar_veiculo(caracteristicas="Meu carro pendente")
        outro = self.criar_veiculo(
            proprietario=self.outro,
            caracteristicas="Carro privado de outro dono",
        )
        response = self.client.get(self.lista_url, {
            "proprietario": self.outro.pk, "pk": outro.pk,
        })
        self.assertEqual(list(response.context["veiculos"]), [proprio])
        self.assertContains(response, "Meu carro pendente")
        self.assertNotContains(response, "Carro privado de outro dono")
        self.assertIn("no-store", response["Cache-Control"])

    def test_lista_vazia(self):
        response = self.client.get(self.lista_url)
        self.assertContains(response, "Nenhum veículo cadastrado")
        self.assertContains(response, f'href="{self.url}"')

    def test_lista_preservada_se_aprovacao_da_identidade_for_revogada(self):
        proprio = self.criar_veiculo()
        Usuario.objects.filter(pk=self.proprietario.pk).update(
            aprovacao_documento="rejeitado",
        )
        response = self.client.get(self.lista_url)
        self.assertEqual(list(response.context["veiculos"]), [proprio])
        self.assertFalse(response.context["pode_anunciar"])
        self.assertNotContains(response, ">Cadastrar veículo</a>")
        self.assertContains(response, reverse("contas:perfil"))

    def test_lista_paginada(self):
        for indice in range(11):
            self.criar_veiculo(caracteristicas=f"Veículo próprio {indice}")
        response = self.client.get(self.lista_url)
        self.assertEqual(len(response.context["veiculos"]), 10)
        self.assertEqual(response.context["paginator"].count, 11)
        self.assertContains(response, 'href="?page=2"')
        response = self.client.get(self.lista_url, {"page": 2})
        self.assertEqual(len(response.context["veiculos"]), 1)

    def test_lista_exibe_status_e_so_vincula_anuncio_publicado(self):
        publicado = self.criar_veiculo(aprovacao="aprovado")
        pendente = self.criar_veiculo()
        rejeitado = self.criar_veiculo(aprovacao="rejeitado")
        bloqueado = self.criar_veiculo(aprovacao="aprovado", bloqueado=True)
        inativo = self.criar_veiculo(aprovacao="aprovado", ativo=False)
        response = self.client.get(self.lista_url)
        self.assertContains(response, "Pendente")
        self.assertContains(response, "Rejeitado")
        self.assertContains(response, "Bloqueado")
        self.assertContains(response, "Inativo")
        url_publico = reverse("core:detalhes", args=[publicado.pk])
        self.assertContains(response, f'href="{url_publico}"')
        for veiculo in (pendente, rejeitado, bloqueado, inativo):
            url = reverse("core:detalhes", args=[veiculo.pk])
            self.assertNotContains(response, f'href="{url}"')

    def test_listagem_nao_aceita_post(self):
        response = self.client.post(self.lista_url, self.dados)
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Veiculo.objects.exists())

    def test_descricao_e_escapada_na_listagem(self):
        self.criar_veiculo(caracteristicas="<script>alert(1)</script>")
        response = self.client.get(self.lista_url)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_painel_da_acesso_a_meus_veiculos(self):
        self.criar_veiculo()
        response = self.client.get(reverse("contas:painel"))
        self.assertContains(response, f'href="{self.lista_url}"')
