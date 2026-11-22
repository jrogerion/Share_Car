from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.test import TestCase
from django.urls import reverse

from apps.contas.models import Usuario


AUTORES = "Projeto desenvolvido por José Rogerio, Luana Corrêa e Pablo Silva."
SECOES = ("como-funciona", "vantagens", "para-proprietarios")


class SobreParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.no_footer = False
        self.links_footer = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "footer" and "site-footer" in attrs.get("class", "").split():
            self.no_footer = True
        if tag == "a" and self.no_footer:
            self.links_footer.append(attrs.get("href", ""))
        if "id" in attrs:
            self.ids.append(attrs["id"])

    def handle_endtag(self, tag):
        if tag == "footer":
            self.no_footer = False


class PaginaSobreTests(TestCase):
    def test_pagina_publica_estatica_sem_consultas(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("core:sobre"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/sobre.html")
        self.assertContains(response, AUTORES)
        self.assertContains(response, "As notas são liberadas quando as duas partes")

    def test_links_do_footer_apontam_para_secoes_existentes(self):
        pagina = self.client.get(reverse("core:sobre"))
        parser = SobreParser()
        parser.feed(pagina.content.decode())
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for rota in ("core:home", "core:entrar", "core:sobre"):
            footer = SobreParser()
            response = self.client.get(reverse(rota))
            footer.feed(response.content.decode())
            self.assertContains(response, AUTORES)
            for secao in SECOES:
                href = reverse("core:sobre") + "#" + secao
                self.assertIn(href, footer.links_footer)
                destino = urlsplit(href)
                self.assertEqual(self.client.get(destino.path).status_code, 200)
                self.assertIn(destino.fragment, parser.ids)

    def test_informacoes_sem_avisos_de_demonstracao_ou_promessas_inexistentes(self):
        response = self.client.get(reverse("core:sobre"))
        for texto in (
            "Ambiente de demonstração", "Projeto acadêmico", "pagamentos simulados",
            "análise documental manual", "seguro incluso", "garantia de renda",
        ):
            self.assertNotContains(response, texto)
        self.assertContains(response, reverse("contas:cadastro"))
        self.assertContains(response, reverse("core:resultados"))

    def test_avisos_operacionais_permanecem(self):
        response = self.client.get(reverse("core:pagamento"))
        self.assertContains(response, "Ambiente de demonstração")

    def test_chamada_respeita_o_papel_da_conta(self):
        usuario = Usuario.objects.create_user("leitor-sobre", "leitor@example.com")
        self.client.force_login(usuario)
        response = self.client.get(reverse("core:sobre"))
        self.assertContains(response, "Preparar meu anúncio")
        usuario.is_staff = True
        usuario.save(update_fields=["is_staff"])
        response = self.client.get(reverse("core:sobre"))
        self.assertContains(response, "Voltar ao painel")
        self.assertNotContains(response, "Preparar meu anúncio")

    def test_pagina_nao_aceita_operacoes_de_escrita(self):
        self.assertEqual(self.client.post(reverse("core:sobre"), {}).status_code, 405)
