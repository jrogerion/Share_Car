from io import BytesIO
from datetime import date, timedelta
from unittest.mock import patch

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.contas.models import Usuario
from apps.avaliacoes.models import Avaliacao
from apps.reservas.models import Reserva
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

    def avaliar(self, carro, indice, nota, reciproca=True, status="concluida"):
        locatario = Usuario.objects.create_user(f"loc-home-{carro.pk}-{indice}")
        inicio = date(2026, 1, 1) + timedelta(days=indice * 3)
        reserva = Reserva.objects.create(
            veiculo=carro, locatario=locatario, inicio=inicio,
            fim=inicio + timedelta(days=1), status=status,
            preco_diaria="150.00", valor_diarias="150.00", total="150.00",
            taxas=0, percentual_comissao="15.00",
        )
        Avaliacao.objects.create(reserva=reserva, autor=locatario, avaliado=self.dono, nota=nota)
        if reciproca:
            Avaliacao.objects.create(reserva=reserva, autor=self.dono, avaliado=locatario, nota=1)

    def test_carrossel_mostra_media_publica_e_total_iguais_aos_detalhes(self):
        carro = self.carro()
        self.avaliar(carro, 0, 5)
        self.avaliar(carro, 1, 4)
        self.avaliar(carro, 2, 1, reciproca=False)
        self.avaliar(carro, 3, 1, status="aceita")
        outro = self.carro()
        self.avaliar(outro, 0, 2)
        with self.assertNumQueries(2):
            response = self.client.get(reverse("core:home"))
        destaque = next(item for item in response.context["destaques"] if item.pk == carro.pk)
        self.assertEqual(destaque.media_avaliacoes, 4.5)
        self.assertEqual(destaque.total_avaliacoes, 2)
        self.assertContains(response, "Avaliação média: 4,5 de 5, com 2 avaliações")
        detalhes = self.client.get(reverse("core:detalhes", args=[carro.pk]))
        self.assertEqual(detalhes.context["avaliacoes"], {"media": 4.5, "total": 2})

    def test_avaliacao_unilateral_nao_libera_nota_no_carrossel(self):
        carro = self.carro()
        self.avaliar(carro, 0, 5, reciproca=False)
        response = self.client.get(reverse("core:home"))
        destaque = response.context["destaques"][0]
        self.assertEqual(destaque.total_avaliacoes, 0)
        self.assertIsNone(destaque.media_avaliacoes)
        self.assertContains(response, "Sem avaliações")
        self.assertNotContains(response, "Avaliação média:")

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
        self.assertNotContains(response, 'data-carousel-toggle')

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
