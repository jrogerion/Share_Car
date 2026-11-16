from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image

from apps.contas.models import Usuario


class PWAPublicaTests(SimpleTestCase):
    def test_manifesto_publico_com_escopo_e_icones(self):
        response = self.client.get(reverse("core:manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        dados = response.json()
        self.assertEqual(dados["start_url"], reverse("core:home"))
        self.assertEqual(dados["scope"], reverse("core:home"))
        self.assertEqual(dados["display"], "standalone")
        self.assertEqual(dados["lang"], "pt-BR")
        self.assertEqual(
            {icone["sizes"] for icone in dados["icons"]}, {"192x192", "512x512"},
        )

    def test_icones_reutilizados_tem_dimensoes_corretas(self):
        for tamanho in (192, 512):
            caminho = finders.find(f"icons/icon-{tamanho}.png")
            self.assertIsNotNone(caminho)
            with Image.open(caminho) as imagem:
                self.assertEqual(imagem.size, (tamanho, tamanho))
                self.assertEqual(imagem.format, "PNG")

    def test_worker_na_raiz_atualiza_sem_cache_http(self):
        response = self.client.get(reverse("core:service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/javascript"))
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["Service-Worker-Allowed"], reverse("core:home"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertContains(response, 'name.startsWith(CACHE_PREFIX)')
        self.assertContains(response, 'credentials: "omit"')
        self.assertContains(response, 'request.method !== "GET"')
        self.assertContains(response, 'request.mode !== "navigate"')
        self.assertContains(response, 'cache: "no-store"')
        self.assertContains(response, reverse("core:offline"))

    def test_tela_offline_independente_de_cdn_sessao_e_scripts(self):
        response = self.client.get(reverse("core:offline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sem conexão com o servidor")
        self.assertContains(response, "Nenhuma operação é salva ou reenviada")
        for conteudo in (
            "<script", "<form", "csrfmiddlewaretoken", "navigation-account",
            "cdn.jsdelivr.net", "fonts.googleapis.com",
        ):
            self.assertNotContains(response, conteudo)
        self.assertNotIn("sessionid", response.cookies)
        self.assertNotIn("csrftoken", response.cookies)

    def test_rotas_pwa_nao_recebem_operacoes(self):
        for rota in ("manifest", "service_worker", "offline"):
            with self.subTest(rota=rota):
                response = self.client.post(reverse(f"core:{rota}"))
                self.assertEqual(response.status_code, 405)


class PWAIndependenteDaContaTests(TestCase):
    def test_paginas_incluem_manifesto_e_registro_uma_vez(self):
        for rota in ("core:home", "core:entrar"):
            response = self.client.get(reverse(rota))
            self.assertContains(response, 'rel="manifest"', count=1)
            self.assertContains(response, 'js/pwa.js', count=1)
            self.assertContains(response, 'data-service-worker-url=', count=1)

    def test_conteudo_cacheavel_nao_muda_apos_login(self):
        rotas = [reverse(f"core:{nome}") for nome in (
            "manifest", "service_worker", "offline",
        )]
        publicos = {url: self.client.get(url).content for url in rotas}
        usuario = Usuario.objects.create_user(
            "usuario-pwa", "usuario-pwa@example.com", first_name="Nome privado",
        )
        self.client.force_login(usuario)

        for url in rotas:
            response = self.client.get(url)
            self.assertEqual(response.content, publicos[url])
            self.assertNotContains(response, usuario.email)
            self.assertNotContains(response, usuario.first_name)
