from io import BytesIO
from unittest.mock import patch

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.contas.models import Usuario
from apps.veiculos.models import FotoVeiculo, Veiculo


class HomeCarouselTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dono = Usuario.objects.create_user(
            "dono-home", "dono-home@example.com",
        )

    def setUp(self):
        troca = patch.object(
            FotoVeiculo._meta.get_field("foto"), "storage", InMemoryStorage(),
        )
        troca.start()
        self.addCleanup(troca.stop)

    def carro(self, **dados):
        return Veiculo.objects.create(**{
            "proprietario": self.dono, "caracteristicas": "Modelo fictício",
            "cidade": "Campinas", "categoria": "Hatch", "cambio": "Manual",
            "combustivel": "Flex", "passageiros": 5, "preco_diaria": "150.00",
            "aprovacao": Veiculo.Aprovacao.APROVADO, **dados,
        })

    def foto(self, carro, nome):
        buffer = BytesIO()
        Image.new("RGB", (2, 2)).save(buffer, format="PNG")
        return FotoVeiculo.objects.create(
            veiculo=carro, foto=SimpleUploadedFile(
                nome, buffer.getvalue(), content_type="image/png",
            ),
        )

    def test_exibe_apenas_anuncios_publicos_com_links_reais(self):
        publicado = self.carro()
        privados = [
            self.carro(ativo=False), self.carro(bloqueado=True),
            self.carro(aprovacao=Veiculo.Aprovacao.PENDENTE),
            self.carro(aprovacao=Veiculo.Aprovacao.REJEITADO),
        ]
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.context["destaques"], [publicado])
        self.assertContains(
            response, f'href="{reverse("core:detalhes", args=[publicado.pk])}"',
        )
        for carro in privados:
            self.assertNotContains(
                response, f'href="{reverse("core:detalhes", args=[carro.pk])}"',
            )
        self.assertNotContains(response, "Exemplos ilustrativos")
        self.assertNotContains(response, "Nota ilustrativa")

    def test_limita_a_oito_recentes_sem_repetir_cards(self):
        carros = [self.carro() for _ in range(10)]
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.context["destaques"], list(reversed(carros[2:])))
        self.assertContains(response, 'class="discovery-car"', count=8)

    def test_usa_primeira_foto_sem_consulta_por_anuncio(self):
        capas = []
        laterais = []
        for _ in range(8):
            carro = self.carro()
            capas.append(self.foto(carro, "frente.png"))
            laterais.append(self.foto(carro, "lateral.png"))

        with self.assertNumQueries(2):
            response = self.client.get(reverse("core:home"))

        for foto in capas:
            self.assertContains(response, foto.foto.url, count=1)
        for foto in laterais:
            self.assertNotContains(response, foto.foto.url)
        self.assertContains(response, 'loading="lazy"', count=8)

    def test_sem_foto_mantem_ilustracao_e_mostra_preco_cadastrado(self):
        self.carro(preco_diaria="321.50")
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "images/car.svg", count=1)
        self.assertContains(response, "R$ 321,50")
        self.assertContains(response, 'class="discovery-car"', count=1)
        self.assertContains(response, 'data-carousel-toggle')

    def test_sem_anuncios_exibe_estado_vazio_sem_carrossel(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("core:home"))

        self.assertContains(response, "Ainda não há veículos publicados")
        self.assertNotContains(response, 'data-discovery-carousel')
        self.assertContains(response, 'href="' + reverse("core:veiculo") + '"')

    def test_texto_do_anuncio_e_escapado(self):
        self.carro(
            categoria='<script>alert(1)</script>',
            caracteristicas='<img src=x onerror=alert(1)>',
        )
        response = self.client.get(reverse("core:home"))

        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, '<img src=x onerror=alert(1)>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
