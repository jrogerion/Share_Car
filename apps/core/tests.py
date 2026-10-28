from django.test import SimpleTestCase
from django.urls import reverse


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
