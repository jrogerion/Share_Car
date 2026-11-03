import base64
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Usuario

from .models import FotoVeiculo, PeriodoAgenda, Veiculo


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Wl2n0kAAAAASUVORK5CYII="
)
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class VeiculosAPITests(TestCase):
    """Endpoints públicos de listagem e detalhe de veículos."""

    @classmethod
    def setUpTestData(cls):
        cls.proprietario = Usuario.objects.create_user(
            username="proprietario-secreto",
            email="proprietario.secreto@example.com",
            password="senha-de-teste",
            first_name="Nome",
            last_name="Sensível",
            proprietario=True,
        )

        def criar_veiculo(**dados):
            padrao = {
                "proprietario": cls.proprietario,
                "caracteristicas": "Veículo de teste",
                "cidade": "São Paulo",
                "categoria": "Hatch",
                "cambio": "Manual",
                "combustivel": "Flex",
                "passageiros": 5,
                "preco_diaria": "150.00",
                "ativo": True,
                "bloqueado": False,
                "aprovacao": Veiculo.Aprovacao.APROVADO,
            }
            padrao.update(dados)
            return Veiculo.objects.create(**padrao)

        cls.hatch = criar_veiculo(
            caracteristicas="Hatch público de São Paulo",
        )
        cls.suv = criar_veiculo(
            caracteristicas="SUV público de São Paulo",
            categoria="SUV",
            cambio="Automático",
            combustivel="Diesel",
            passageiros=7,
            preco_diaria="250.00",
        )
        cls.rio_suv = criar_veiculo(
            caracteristicas="SUV público do Rio de Janeiro",
            cidade="Rio de Janeiro",
            categoria="SUV",
            cambio="Automático",
            combustivel="Flex",
            preco_diaria="200.00",
        )
        cls.pendente = criar_veiculo(
            categoria="Picape",
            aprovacao=Veiculo.Aprovacao.PENDENTE,
        )
        cls.bloqueado = criar_veiculo(bloqueado=True)
        cls.inativo = criar_veiculo(ativo=False)

        cls.foto_hatch = FotoVeiculo.objects.create(
            veiculo=cls.hatch,
            foto=SimpleUploadedFile(
                "hatch.png", PNG_1X1, content_type="image/png",
            ),
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def listar(self, **filtros):
        return self.client.get(
            reverse("veiculos_api:lista"),
            filtros,
        )

    def detalhar(self, veiculo):
        return self.client.get(
            reverse("veiculos_api:detalhe", args=[veiculo.pk]),
        )

    def test_lista_somente_veiculos_publicos(self):
        response = self.listar()

        self.assertEqual(response.status_code, 200)
        dados = response.json()
        self.assertEqual(dados["count"], 3)
        ids = {item["id"] for item in dados["results"]}
        self.assertEqual(
            ids,
            {self.hatch.pk, self.suv.pk, self.rio_suv.pk},
        )
        for item in dados["results"]:
            self.assertNotIn("proprietario", item)

    def test_filtros_individuais(self):
        casos = (
            ({"cidade": "são paulo"}, {self.hatch.pk, self.suv.pk}),
            ({"categoria": "SUV"}, {self.suv.pk, self.rio_suv.pk}),
            ({"cambio": "Manual"}, {self.hatch.pk}),
            ({"combustivel": "Diesel"}, {self.suv.pk}),
            ({"passageiros": 7}, {self.suv.pk}),
            ({"diaria_min": "200.00"}, {self.suv.pk, self.rio_suv.pk}),
            ({"diaria_max": "200.00"}, {self.hatch.pk, self.rio_suv.pk}),
            (
                {"diaria_min": "160.00", "diaria_max": "220.00"},
                {self.rio_suv.pk},
            ),
        )

        for filtros, esperado in casos:
            with self.subTest(filtros=filtros):
                response = self.listar(**filtros)
                self.assertEqual(response.status_code, 200)
                dados = response.json()
                ids = {item["id"] for item in dados["results"]}
                self.assertEqual(ids, esperado)

    def test_filtros_combinados(self):
        response = self.listar(
            cidade="São Paulo",
            categoria="SUV",
            cambio="Automático",
            combustivel="Diesel",
            passageiros=7,
            diaria_min="200.00",
            diaria_max="300.00",
        )

        self.assertEqual(response.status_code, 200)
        dados = response.json()
        self.assertEqual(dados["count"], 1)
        self.assertEqual(dados["results"][0]["id"], self.suv.pk)

    def test_categoria_sem_veiculos_retorna_lista_vazia(self):
        response = self.listar(categoria="Picape")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_filtro_invalido_retorna_400(self):
        response = self.listar(passageiros="muitos")

        self.assertEqual(response.status_code, 400)
        self.assertIn("passageiros", response.json())

    def test_faixa_de_diaria_invalida_retorna_400(self):
        response = self.listar(diaria_min="300.00", diaria_max="100.00")

        self.assertEqual(response.status_code, 400)
        erros = response.json()
        self.assertIn("diaria_max", erros)
        self.assertIn("maior ou igual", str(erros["diaria_max"]))

    def test_paginacao(self):
        self.criar_veiculos_campinas(7)
        response = self.listar(cidade="Campinas")

        dados = response.json()
        self.assertEqual(dados["count"], 7)
        self.assertEqual(len(dados["results"]), 6)
        self.assertIsNotNone(dados["next"])
        self.assertIsNone(dados["previous"])
        self.assertIn("cidade=Campinas", dados["next"])

        segunda_pagina = self.listar(cidade="Campinas", page=2).json()
        self.assertEqual(segunda_pagina["count"], 7)
        self.assertEqual(len(segunda_pagina["results"]), 1)
        self.assertIsNotNone(segunda_pagina["previous"])

    def test_tamanho_da_pagina_pode_ser_ajustado(self):
        self.criar_veiculos_campinas(7)
        response = self.listar(cidade="Campinas", page_size=3)

        dados = response.json()
        self.assertEqual(dados["count"], 7)
        self.assertEqual(len(dados["results"]), 3)

    def test_detalhe_de_veiculo_publico(self):
        response = self.detalhar(self.hatch)

        self.assertEqual(response.status_code, 200)
        dados = response.json()
        self.assertEqual(dados["id"], self.hatch.pk)
        self.assertEqual(
            dados["caracteristicas"],
            "Hatch público de São Paulo",
        )
        self.assertEqual(dados["preco_diaria"], "150.00")
        self.assertEqual(len(dados["fotos"]), 1)
        self.assertTrue(
            dados["fotos"][0]["url"].startswith(
                "http://testserver/media/",
            )
        )
        self.assertNotIn("proprietario", dados)

    def test_detalhe_de_veiculo_sem_fotos(self):
        response = self.detalhar(self.rio_suv)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fotos"], [])

    def test_detalhe_de_veiculo_nao_publico_retorna_404(self):
        for nome, veiculo in (
            ("pendente", self.pendente),
            ("bloqueado", self.bloqueado),
            ("inativo", self.inativo),
        ):
            with self.subTest(nome=nome):
                response = self.detalhar(veiculo)
                self.assertEqual(response.status_code, 404)

    def test_detalhe_inexistente_retorna_404(self):
        response = self.client.get(
            reverse("veiculos_api:detalhe", args=[999999]),
        )

        self.assertEqual(response.status_code, 404)

    def test_nao_expoe_dados_do_proprietario(self):
        respostas = (self.listar(), self.detalhar(self.hatch))

        for response in respostas:
            conteudo = response.content.decode()
            with self.subTest(endpoint=response.request["PATH_INFO"]):
                self.assertNotIn("proprietario-secreto", conteudo)
                self.assertNotIn(
                    "proprietario.secreto@example.com",
                    conteudo,
                )
                self.assertNotIn("Sensível", conteudo)

    def test_lista_nao_aceita_post(self):
        response = self.client.post(reverse("veiculos_api:lista"))

        self.assertEqual(response.status_code, 405)

    def test_detalhe_nao_aceita_post(self):
        response = self.client.post(
            reverse("veiculos_api:detalhe", args=[self.hatch.pk]),
        )

        self.assertEqual(response.status_code, 405)

    def periodo(self, dias_inicio=5, duracao=3):
        inicio = timezone.localdate() + timedelta(days=dias_inicio)
        return inicio, inicio + timedelta(days=duracao)

    def test_filtra_por_periodo_bloqueado(self):
        inicio, fim = self.periodo()
        PeriodoAgenda.objects.create(
            veiculo=self.hatch,
            inicio=inicio,
            fim=fim,
            tipo=PeriodoAgenda.Tipo.BLOQUEADO,
        )

        response = self.listar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["results"]}
        self.assertNotIn(self.hatch.pk, ids)
        self.assertEqual(ids, {self.suv.pk, self.rio_suv.pk})

    def test_filtra_por_periodo_disponivel(self):
        inicio, fim = self.periodo()

        response = self.listar(
            retirada=inicio.isoformat(),
            devolucao=fim.isoformat(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

    def test_periodo_incompleto_retorna_400(self):
        inicio, _ = self.periodo()

        response = self.listar(retirada=inicio.isoformat())

        self.assertEqual(response.status_code, 400)
        self.assertIn("devolucao", response.json())

    def test_periodo_invertido_retorna_400(self):
        inicio, fim = self.periodo()

        response = self.listar(
            retirada=fim.isoformat(),
            devolucao=inicio.isoformat(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("devolucao", response.json())

    def criar_veiculos_campinas(self, quantidade: int):
        for indice in range(1, quantidade + 1):
            Veiculo.objects.create(
                proprietario=self.proprietario,
                caracteristicas=f"Paginação {indice}",
                cidade="Campinas",
                categoria="Hatch",
                cambio="Manual",
                combustivel="Flex",
                passageiros=5,
                preco_diaria="150.00",
                ativo=True,
                bloqueado=False,
                aprovacao=Veiculo.Aprovacao.APROVADO,
            )
