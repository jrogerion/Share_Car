from itertools import product

from django.test import TestCase
from django.urls import reverse

from apps.contas.models import Usuario

from .consultas import buscar_veiculos, veiculos_publicos
from .models import Veiculo


class BuscaCidadePublicacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dono = Usuario.objects.create_user(
            "dono-busca", "dono@example.com", proprietario=True,
        )
        cls.veiculo = Veiculo.objects.create(
            proprietario=cls.dono,
            caracteristicas="Carro de teste Maria da Fé",
            cidade="Maria da Fé", categoria="Hatch", cambio="Manual",
            combustivel="Flex", passageiros=5, preco_diaria="150.00",
            aprovacao="aprovado",
        )

    def test_busca_cidade_sem_acentos_no_site_e_api(self):
        for cidade in (
            "Maria da Fe", "MARIA DA FE", "  maria da fe  ", "da Fe",
        ):
            for rota in ("core:resultados", "veiculos_api:lista"):
                with self.subTest(cidade=cidade, rota=rota):
                    response = self.client.get(
                        reverse(rota), {"cidade": cidade},
                    )
                    self.assertEqual(response.status_code, 200)
                    if rota == "veiculos_api:lista":
                        self.assertEqual(response.json()["count"], 1)
                        self.assertEqual(
                            response.json()["results"][0]["id"],
                            self.veiculo.pk,
                        )
                    else:
                        self.assertContains(
                            response, "Carro de teste Maria da Fé",
                        )
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.cidade, "Maria da Fé")

    def test_acentos_em_ambos_os_lados_e_resultado_inexistente(self):
        for cadastrada, busca in (
            ("São Paulo", "Sao Paulo"), ("Sao Paulo", "São Paulo"),
            ("Conceição", "CONCEICAO"),
        ):
            with self.subTest(cadastrada=cadastrada):
                Veiculo.objects.filter(pk=self.veiculo.pk).update(
                    cidade=cadastrada,
                )
                self.assertEqual(
                    list(buscar_veiculos(cidade=busca)), [self.veiculo],
                )
        self.assertFalse(buscar_veiculos(cidade="Cidade inexistente").exists())

    def test_busca_sem_acentos_preserva_demais_filtros(self):
        self.assertEqual(buscar_veiculos(
            cidade="Maria da Fe", categoria="Hatch", passageiros_min=5,
        ).count(), 1)
        self.assertFalse(buscar_veiculos(
            cidade="Maria da Fe", categoria="SUV",
        ).exists())

    def test_motivos_correspondem_a_visibilidade_publica(self):
        for aprovacao, ativo, bloqueado in product(
            Veiculo.Aprovacao.values, (True, False), (True, False),
        ):
            with self.subTest(
                aprovacao=aprovacao, ativo=ativo, bloqueado=bloqueado,
            ):
                Veiculo.objects.filter(pk=self.veiculo.pk).update(
                    aprovacao=aprovacao, ativo=ativo, bloqueado=bloqueado,
                )
                self.veiculo.refresh_from_db()
                publicado = veiculos_publicos().filter(
                    pk=self.veiculo.pk,
                ).exists()
                self.assertEqual(
                    not self.veiculo.motivos_nao_publicacao, publicado,
                )
                if not publicado:
                    self.assertFalse(
                        buscar_veiculos(cidade="Maria da Fe").exists(),
                    )

    def test_proprietario_consulta_todos_os_impedimentos(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(
            aprovacao="rejeitado", ativo=False, bloqueado=True,
        )
        self.client.force_login(self.dono)
        response = self.client.get(reverse("veiculos:meus"))
        self.assertContains(response, "Anúncio rejeitado.")
        self.assertContains(response, "Anúncio desativado pelo proprietário.")
        self.assertContains(response, "Anúncio bloqueado pela administração.")
        self.assertNotContains(response, "Publicado na busca.")
