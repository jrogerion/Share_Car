from html.parser import HTMLParser

from django.test import SimpleTestCase
from django.urls import reverse


class NavigationParser(HTMLParser):
    """Extrai os links por região, sem depender de bibliotecas externas."""

    def __init__(self):
        super().__init__()
        self.region = None
        self.links = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "nav":
            self.region = attributes.get("aria-label")
            self.links.setdefault(self.region, [])
        elif tag == "a" and self.region:
            self.links[self.region].append(attributes)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.region = None


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
                if page != "home":
                    self.assertContains(response, "Dados fictícios.")
                    self.assertContains(response, "css/pages.css")

    def test_demo_pages_do_not_accept_submissions(self):
        for page in self.pages:
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
