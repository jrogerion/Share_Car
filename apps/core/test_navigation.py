from django.test import Client, TestCase
from django.urls import reverse

from apps.contas.models import Usuario

from .tests import NavigationParser


class MenuLayoutParser(NavigationParser):
    """Identifica o grupo de cada controle, além da região de navegação."""

    def __init__(self):
        super().__init__()
        self.divs = []
        self.controls = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "div":
            self.divs.append(set(attributes.get("class", "").split()))
        super().handle_starttag(tag, attrs)
        if tag in ("a", "form") and self.region:
            self.controls.append({
                "region": self.region, "tag": tag, "attrs": attributes,
                "groups": set().union(*self.divs),
            })

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == "div":
            self.divs.pop()


class AccountNavigationTests(TestCase):
    regions = ("Navegação principal", "Navegação mobile")

    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            "identificador-interno", "pessoa@example.com", first_name="Marina",
        )

    def menu(self, response):
        parser = MenuLayoutParser()
        parser.feed(response.content.decode())
        return parser

    def test_visitante_tem_um_unico_entrar_por_regiao(self):
        response = self.client.get(reverse("core:home"))
        self.assertTemplateUsed(
            response, "core/includes/navigation_account.html",
        )
        parser = self.menu(response)
        for region in self.regions:
            with self.subTest(region=region):
                links = parser.links[region]
                self.assertEqual(sum(
                    link["href"] == reverse("core:entrar") for link in links
                ), 1)
                self.assertEqual(parser.forms[region], [])
        self.assertNotContains(response, "navigation-user-name")
        entrar = next(control for control in parser.controls if (
            control["region"] == "Navegação principal"
            and control["attrs"].get("href") == reverse("core:entrar")
        ))
        self.assertIn("site-account", entrar["groups"])
        self.assertNotIn("navigation-main", entrar["groups"])

    def test_conta_fica_separada_do_menu_sem_duplicar_acoes(self):
        self.client.force_login(self.usuario)
        for rota in ("core:home", "contas:perfil", "reservas:minhas"):
            with self.subTest(rota=rota):
                response = self.client.get(reverse(rota))
                self.assertContains(response, ">Marina</span>", count=2)
                parser = self.menu(response)
                for region in self.regions:
                    links = [link["href"] for link in parser.links[region]]
                    self.assertEqual(links.count(reverse("contas:perfil")), 1)
                    self.assertEqual(links.count(reverse("contas:painel")), 1)
                    self.assertNotIn(reverse("core:entrar"), links)
                    self.assertEqual(len(parser.forms[region]), 1)
                    form = parser.forms[region][0]
                    self.assertEqual(form["attrs"]["method"], "post")
                    self.assertEqual(form["attrs"]["action"], reverse("core:sair"))
                    self.assertEqual(len(form["buttons"]), 1)
                    self.assertEqual(form["buttons"][0]["type"], "submit")
                    self.assertEqual(
                        form["buttons"][0]["aria-label"], "Sair da conta",
                    )
                for control in parser.controls:
                    if control["region"] != "Navegação principal":
                        continue
                    destino = control["attrs"].get("href")
                    if destino == reverse("contas:perfil") or control["tag"] == "form":
                        self.assertIn("site-account", control["groups"])
                        self.assertNotIn("navigation-main", control["groups"])
                    elif destino in (
                        reverse("core:resultados"), reverse("contas:painel"),
                    ):
                        self.assertIn("navigation-main", control["groups"])

    def test_staff_preserva_acesso_a_administracao_sem_conta_duplicada(self):
        self.usuario.is_staff = True
        self.usuario.save(update_fields=["is_staff"])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:home"))
        parser = self.menu(response)
        for region in self.regions:
            links = [link["href"] for link in parser.links[region]]
            self.assertEqual(links.count(reverse("administracao:painel")), 1)
            self.assertEqual(links.count(reverse("contas:perfil")), 1)
            self.assertEqual(len(parser.forms[region]), 1)

    def test_nome_ausente_preserva_link_sem_expor_email_ou_username(self):
        self.usuario.first_name = ""
        self.usuario.save(update_fields=["first_name"])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, ">Minha conta</span>", count=2)
        self.assertNotContains(response, self.usuario.email)
        self.assertNotContains(response, self.usuario.username)

    def test_nome_longo_preservado_e_html_escapado(self):
        self.usuario.first_name = "M" * 150
        self.usuario.save(update_fields=["first_name"])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, f">{self.usuario.first_name}</span>", count=2)
        self.usuario.first_name = '\"><script>alert(1)</script>'
        self.usuario.save(update_fields=["first_name"])
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_logout_de_ambas_as_navegacoes_com_csrf(self):
        for region in self.regions:
            with self.subTest(region=region):
                client = Client(enforce_csrf_checks=True)
                client.force_login(self.usuario)
                response = client.get(reverse("core:home"))
                form = self.menu(response).forms[region][0]
                token = next(
                    field["value"] for field in form["inputs"]
                    if field.get("name") == "csrfmiddlewaretoken"
                )
                action = form["attrs"]["action"]
                self.assertEqual(client.post(action).status_code, 403)
                self.assertIn("_auth_user_id", client.session)
                response = client.post(action, {"csrfmiddlewaretoken": token})
                self.assertRedirects(response, reverse("core:home"))
                self.assertNotIn("_auth_user_id", client.session)
                parser = self.menu(client.get(reverse("core:home")))
                for navigation_region in self.regions:
                    self.assertEqual(parser.forms[navigation_region], [])
                    self.assertEqual(sum(
                        link["href"] == reverse("core:entrar")
                        for link in parser.links[navigation_region]
                    ), 1)
