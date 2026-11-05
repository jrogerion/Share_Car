from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse


class NavigationParser(HTMLParser):
    """Extrai os links por região, sem depender de bibliotecas externas."""

    def __init__(self):
        super().__init__()
        self.region = None
        self.links = {}
        self.forms = {}
        self.form = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "nav":
            self.region = attributes.get("aria-label")
            self.links.setdefault(self.region, [])
            self.forms.setdefault(self.region, [])
        elif tag == "a" and self.region:
            self.links[self.region].append(attributes)
        elif tag == "form" and self.region:
            self.form = {"attrs": attributes, "inputs": [], "buttons": []}
            self.forms[self.region].append(self.form)
        elif tag in ("input", "button") and self.form is not None:
            self.form[f"{tag}s"].append(attributes)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.region = None
        elif tag == "form":
            self.form = None


class TemplatePagesTests(SimpleTestCase):
    """As prévias devem renderizar e navegar sem acesso ao banco."""

    pages = (
        "home", "entrar", "resultados", "detalhes", "resumo",
        "pagamento", "reservas", "checkin", "veiculo", "avaliacao",
    )

    def test_pages_render_without_database(self):
        for page in self.pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, f"core/{page}.html")
                self.assertContains(response, 'id="conteudo"')
                if page not in ("home", "entrar"):
                    self.assertContains(response, "Dados fictícios.")
                    self.assertContains(response, "css/pages.css")

    def test_demo_pages_do_not_accept_submissions(self):
        for page in self.pages:
            if page == "entrar":
                continue
            with self.subTest(page=page):
                response = self.client.post(reverse(f"core:{page}"))
                self.assertEqual(response.status_code, 405)

    def test_primary_navigation(self):
        response = self.client.get(reverse("core:home"))
        for page in ("resultados", "reservas", "entrar", "veiculo"):
            with self.subTest(page=page):
                self.assertContains(response, f'href="{reverse(f"core:{page}")}"')

    def test_reservation_demo_flow(self):
        steps = (
            ("resultados", "detalhes"), ("detalhes", "resumo"),
            ("resumo", "pagamento"), ("pagamento", "reservas"),
            ("reservas", "checkin"), ("checkin", "avaliacao"),
            ("avaliacao", "reservas"),
        )
        for source, destination in steps:
            with self.subTest(source=source):
                response = self.client.get(reverse(f"core:{source}"))
                self.assertContains(
                    response, f'href="{reverse(f"core:{destination}")}"',
                )

    def test_shared_navigation_on_all_pages(self):
        for page in self.pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                self.assertTemplateUsed(
                    response, "core/includes/navigation_links.html",
                )
                self.assertContains(
                    response, 'aria-label="Navegação mobile"', count=1,
                )
                self.assertContains(
                    response, 'aria-label="Navegação principal"', count=1,
                )
                parser = NavigationParser()
                parser.feed(response.content.decode())
                mobile = parser.links["Navegação mobile"]
                self.assertEqual(
                    [link["href"] for link in mobile],
                    [reverse(f"core:{name}") for name in (
                        "home", "resultados", "reservas", "entrar",
                    )],
                )

    def test_current_navigation_page_and_section(self):
        sections = {
            "home": "home", "entrar": "entrar",
            "resultados": "resultados", "detalhes": "resultados",
            "resumo": "resultados", "pagamento": "resultados",
            "reservas": "reservas", "checkin": "reservas",
            "avaliacao": "reservas", "veiculo": "veiculo",
        }
        for page, section in sections.items():
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                parser = NavigationParser()
                parser.feed(response.content.decode())
                for region in ("Navegação principal", "Navegação mobile"):
                    current = [
                        link for link in parser.links[region]
                        if "aria-current" in link
                    ]
                    if page == "veiculo" and region == "Navegação mobile":
                        self.assertEqual(current, [])
                        continue
                    self.assertEqual(len(current), 1)
                    self.assertEqual(
                        current[0]["href"], reverse(f"core:{section}"),
                    )
                    self.assertEqual(
                        current[0]["aria-current"],
                        "page" if page == section else "location",
                    )

    def test_shared_fonts_and_icons_loaded_once(self):
        for page in self.pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                self.assertContains(response, "family=Inter", count=1)
                self.assertContains(response, "bootstrap-icons.min.css", count=1)


class AuthenticatedNavigationTests(TestCase):
    regions = ("Navegação principal", "Navegação mobile")

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="identificador-interno", email="pessoa@example.com",
            password="Senha-teste!72rT9", first_name="Marina",
        )

    def parse_navigation(self, response):
        parser = NavigationParser()
        parser.feed(response.content.decode())
        return parser

    def test_visitantes_veem_entrar_sem_formularios_de_logout(self):
        for page in TemplatePagesTests.pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                parser = self.parse_navigation(response)
                for region in self.regions:
                    self.assertEqual(parser.forms[region], [])
                    self.assertIn(
                        reverse("core:entrar"),
                        [link["href"] for link in parser.links[region]],
                    )
                self.assertNotContains(response, "navigation-user-name")

    def test_usuario_identificado_com_logout_em_todas_as_paginas(self):
        self.client.force_login(self.usuario)
        pages = [reverse(f"core:{page}") for page in TemplatePagesTests.pages]
        pages += [
            reverse("contas:cadastro"), reverse("contas:cadastro_concluido"),
            reverse("contas:perfil"),
        ]
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, ">Marina</span>", count=2)
                parser = self.parse_navigation(response)
                for region in self.regions:
                    links = [link["href"] for link in parser.links[region]]
                    self.assertNotIn(reverse("core:entrar"), links)
                    self.assertIn(reverse("contas:perfil"), links)
                    for page in ("home", "resultados", "reservas"):
                        self.assertIn(reverse(f"core:{page}"), links)
                    if region == "Navegação mobile":
                        self.assertEqual(len(links), 4)
                    self.assertEqual(len(parser.forms[region]), 1)
                    form = parser.forms[region][0]
                    self.assertEqual(form["attrs"]["method"], "post")
                    self.assertEqual(
                        form["attrs"]["action"], reverse("contas:sair"),
                    )
                    csrf = [field for field in form["inputs"]
                            if field.get("name") == "csrfmiddlewaretoken"]
                    self.assertEqual(len(csrf), 1)
                    self.assertTrue(csrf[0]["value"])
                    self.assertEqual(form["buttons"][0]["type"], "submit")
                    self.assertEqual(
                        form["buttons"][0]["aria-label"], "Sair da conta",
                    )

    def test_nome_ausente_nao_expoe_email_ou_identificador_interno(self):
        self.usuario.first_name = ""
        self.usuario.save(update_fields=["first_name"])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, ">Minha conta</span>", count=2)
        self.assertNotContains(response, self.usuario.email)
        self.assertNotContains(response, self.usuario.username)

    def test_nome_e_escapado_no_texto_e_no_atributo(self):
        self.usuario.first_name = '\"><script>alert(1)</script>'
        self.usuario.save(update_fields=["first_name"])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_nome_longo_preservado_no_texto_acessivel(self):
        self.usuario.first_name = "M" * 150
        self.usuario.save(update_fields=["first_name"])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, f">{self.usuario.first_name}</span>", count=2)

    def test_logout_dos_dois_menus_com_csrf_e_retorno_ao_estado_anonimo(self):
        for region in self.regions:
            with self.subTest(region=region):
                client = Client(enforce_csrf_checks=True)
                client.force_login(self.usuario)
                response = client.get(reverse("core:home"))
                form = self.parse_navigation(response).forms[region][0]
                token = next(
                    field["value"] for field in form["inputs"]
                    if field.get("name") == "csrfmiddlewaretoken"
                )
                action = form["attrs"]["action"]
                self.assertEqual(client.post(action).status_code, 403)
                self.assertIn("_auth_user_id", client.session)
                response = client.post(action, {"csrfmiddlewaretoken": token})
                self.assertRedirects(response, reverse("core:entrar"))
                self.assertNotIn("_auth_user_id", client.session)
                response = client.get(reverse("core:home"))
                parser = self.parse_navigation(response)
                for navigation_region in self.regions:
                    self.assertEqual(parser.forms[navigation_region], [])
                    self.assertIn(
                        reverse("core:entrar"),
                        [link["href"] for link in parser.links[navigation_region]],
                    )
