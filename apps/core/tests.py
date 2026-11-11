import base64
import shutil
import tempfile
from html.parser import HTMLParser
from urllib.parse import urlencode

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.templatetags.static import static
from django.urls import reverse

from apps.contas.models import Usuario
from apps.core.destaques import DESTAQUES
from apps.veiculos.models import FotoVeiculo, Veiculo


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Wl2n0kAAAAASUVORK5CYII="
)
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


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
        "home", "entrar", "resumo",
        "pagamento", "reservas_exemplo", "checkin", "avaliacao",
    )

    def test_pages_render_without_database(self):
        for page in self.pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                self.assertEqual(response.status_code, 200)
                template = (
                    "core/reservas.html"
                    if page == "reservas_exemplo"
                    else f"core/{page}.html"
                )
                self.assertTemplateUsed(response, template)
                self.assertContains(response, 'id="conteudo"')
                if page not in ("home", "entrar"):
                    self.assertContains(response, "Dados fictícios.")
                    self.assertContains(response, "css/pages.css")

    def test_demo_pages_do_not_accept_submissions(self):
        for page in self.pages:
            if page == "entrar":
                # A autenticação real aceita POST para validar as credenciais.
                continue
            with self.subTest(page=page):
                response = self.client.post(reverse(f"core:{page}"))
                self.assertEqual(response.status_code, 405)

    def test_primary_navigation(self):
        response = self.client.get(reverse("core:home"))
        for page in ("core:resultados", "reservas:minhas", "core:entrar", "core:veiculo"):
            with self.subTest(page=page):
                self.assertContains(response, f'href="{reverse(page)}"')

    def test_home_search_form_targets_results(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'method="get"')
        self.assertContains(response, f'action="{reverse("core:resultados")}"')
        self.assertContains(response, 'role="search"')
        for field in ("cidade", "retirada", "devolucao"):
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"')
        self.assertContains(response, 'type="submit"')
        self.assertContains(response, "Buscar carros")

    def test_home_category_chips_link_to_filtered_results(self):
        response = self.client.get(reverse("core:home"))

        for categoria in ("Hatch", "Sedã", "SUV", "Picape"):
            with self.subTest(categoria=categoria):
                href = (
                    f'{reverse("core:resultados")}?'
                    f'{urlencode({"categoria": categoria})}'
                )
                self.assertContains(response, f'href="{href}"')

    def test_home_destaques_link_to_car_details(self):
        response = self.client.get(reverse("core:home"))

        for carro in DESTAQUES:
            with self.subTest(carro=carro.slug):
                self.assertContains(
                    response,
                    f'href="{reverse("core:destaque", args=[carro.slug])}"',
                )
                self.assertContains(response, carro.nome)

    def test_pagina_de_destaque_exibe_carrossel_e_detalhes(self):
        for carro in DESTAQUES:
            with self.subTest(carro=carro.slug):
                response = self.client.get(
                    reverse("core:destaque", args=[carro.slug]),
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "core/destaque.html")
                self.assertContains(response, carro.nome)
                self.assertContains(response, carro.descricao)
                self.assertContains(response, carro.cidade)
                self.assertContains(response, carro.categoria)
                self.assertContains(response, f"R$ {carro.preco_diaria},00")
                self.assertContains(response, "data-carousel-track")
                self.assertContains(response, "data-carousel-prev")
                self.assertContains(response, "data-carousel-next")
                self.assertContains(response, f"Foto 1 de {len(carro.fotos)}")
                self.assertContains(
                    response,
                    'class="flow-carousel-item',
                    count=len(carro.fotos),
                )
                for foto in carro.fotos:
                    self.assertContains(response, static(foto))

    def test_destaque_inexistente_retorna_404(self):
        response = self.client.get(
            reverse("core:destaque", args=["carro-inexistente"]),
        )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)

    def test_home_search_form_tem_estado_de_carregamento(self):
        response = self.client.get(reverse("core:home"))

        for atributo in (
            "data-search-form",
            "data-search-submit",
            "data-search-spinner",
            "data-search-status",
        ):
            with self.subTest(atributo=atributo):
                self.assertContains(response, atributo)

    def test_reservation_demo_flow(self):
        steps = (
            ("resumo", "pagamento"), ("pagamento", "reservas_exemplo"),
            ("reservas_exemplo", "checkin"), ("checkin", "avaliacao"),
            ("avaliacao", "reservas_exemplo"),
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
                    [
                        reverse("core:home"),
                        reverse("core:resultados"),
                        reverse("reservas:minhas"),
                        reverse("core:entrar"),
                    ],
                )

    def test_current_navigation_page_and_section(self):
        sections = {
            "home": ("core:home", True),
            "entrar": ("core:entrar", True),
            "resumo": ("core:resultados", False),
            "pagamento": ("core:resultados", False),
            "reservas_exemplo": ("reservas:minhas", True),
            "checkin": ("reservas:minhas", False),
            "avaliacao": ("reservas:minhas", False),
        }
        for page, (rota, pagina_atual) in sections.items():
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                parser = NavigationParser()
                parser.feed(response.content.decode())
                for region in ("Navegação principal", "Navegação mobile"):
                    current = [
                        link for link in parser.links[region]
                        if "aria-current" in link
                    ]
                    self.assertEqual(len(current), 1)
                    self.assertEqual(current[0]["href"], reverse(rota))
                    self.assertEqual(
                        current[0]["aria-current"],
                        "page" if pagina_atual else "location",
                    )

    def test_shared_fonts_and_icons_loaded_once(self):
        for page in self.pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"core:{page}"))
                self.assertContains(response, "family=Inter", count=1)
                self.assertContains(response, "bootstrap-icons.min.css", count=1)
                self.assertContains(response, "js/search-loading.js", count=1)


class ResultadosTests(TestCase):
    """A busca deve consultar apenas veículos públicos e combinar filtros."""

    @classmethod
    def setUpTestData(cls):
        proprietario = Usuario.objects.create_user(
            username="proprietario-secreto",
            email="proprietario.secreto@example.com",
            password="senha-de-teste",
            first_name="Nome",
            last_name="Sensível",
            proprietario=True,
        )
        cls.proprietario = proprietario

        def criar_veiculo(**dados):
            padrao = {
                "proprietario": proprietario,
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

        cls.sp_hatch = criar_veiculo(
            caracteristicas="Hatch público de São Paulo",
        )
        cls.sp_suv = criar_veiculo(
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
            passageiros=5,
            preco_diaria="200.00",
        )
        cls.pendente = criar_veiculo(
            caracteristicas="Veículo pendente de aprovação",
            categoria="Picape",
            aprovacao=Veiculo.Aprovacao.PENDENTE,
        )
        cls.bloqueado = criar_veiculo(
            caracteristicas="Veículo bloqueado",
            bloqueado=True,
        )
        cls.inativo = criar_veiculo(
            caracteristicas="Veículo inativo",
            ativo=False,
        )

    def buscar(self, **filtros):
        return self.client.get(reverse("core:resultados"), filtros)

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

    def test_exibe_somente_veiculos_publicos(self):
        response = self.buscar()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hatch público de São Paulo")
        self.assertContains(response, "SUV público de São Paulo")
        self.assertContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "Veículo pendente de aprovação")
        self.assertNotContains(response, "Veículo bloqueado")
        self.assertNotContains(response, "Veículo inativo")

    def test_filtra_por_cidade_sem_diferenciar_maiusculas(self):
        response = self.buscar(cidade="são paulo")

        self.assertContains(response, "Hatch público de São Paulo")
        self.assertContains(response, "SUV público de São Paulo")
        self.assertNotContains(response, "SUV público do Rio de Janeiro")

    def test_filtra_por_categoria(self):
        response = self.buscar(categoria="SUV")

        self.assertContains(response, "SUV público de São Paulo")
        self.assertContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "Hatch público de São Paulo")

    def test_categoria_sem_anuncios_retorna_resultado_vazio(self):
        response = self.buscar(categoria="Picape")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Não foi possível aplicar os filtros.")
        self.assertContains(response, "Nenhum veículo encontrado")
        self.assertContains(response, '<option value="Picape" selected>')

    def test_filtra_por_cambio(self):
        response = self.buscar(cambio="Manual")

        self.assertContains(response, "Hatch público de São Paulo")
        self.assertNotContains(response, "SUV público de São Paulo")

    def test_filtra_por_combustivel(self):
        response = self.buscar(combustivel="Diesel")

        self.assertContains(response, "SUV público de São Paulo")
        self.assertNotContains(response, "Hatch público de São Paulo")
        self.assertNotContains(response, "SUV público do Rio de Janeiro")

    def test_filtra_por_passageiros_minimos(self):
        response = self.buscar(passageiros=7)

        self.assertContains(response, "SUV público de São Paulo")
        self.assertNotContains(response, "Hatch público de São Paulo")
        self.assertNotContains(response, "SUV público do Rio de Janeiro")

    def test_filtra_por_diaria_minima(self):
        response = self.buscar(diaria_min="200.00")

        self.assertContains(response, "SUV público de São Paulo")
        self.assertContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "Hatch público de São Paulo")

    def test_filtra_por_diaria_maxima(self):
        response = self.buscar(diaria_max="200.00")

        self.assertContains(response, "Hatch público de São Paulo")
        self.assertContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "SUV público de São Paulo")
        self.assertNotContains(response, "Veículo pendente de aprovação")
        self.assertNotContains(response, "Veículo bloqueado")
        self.assertNotContains(response, "Veículo inativo")

    def test_filtra_por_faixa_de_diaria(self):
        response = self.buscar(diaria_min="160.00", diaria_max="220.00")

        self.assertContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "Hatch público de São Paulo")
        self.assertNotContains(response, "SUV público de São Paulo")

    def test_combina_faixa_de_diaria_com_outros_filtros(self):
        response = self.buscar(
            cidade="São Paulo",
            categoria="SUV",
            cambio="Automático",
            combustivel="Diesel",
            passageiros=7,
            diaria_min="200.00",
            diaria_max="300.00",
        )

        self.assertContains(response, "SUV público de São Paulo")
        self.assertNotContains(response, "Hatch público de São Paulo")
        self.assertNotContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "Veículo pendente de aprovação")
        self.assertNotContains(response, "Veículo bloqueado")
        self.assertNotContains(response, "Veículo inativo")

    def test_faixa_de_diaria_invalida_nao_quebra_a_pagina(self):
        response = self.buscar(diaria_min="300.00", diaria_max="100.00")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível aplicar os filtros.")
        self.assertContains(
            response,
            "A diária máxima deve ser maior ou igual à mínima.",
        )
        self.assertContains(response, "Nenhum veículo encontrado")

    def test_combina_todos_os_filtros(self):
        response = self.buscar(
            cidade="São Paulo",
            categoria="SUV",
            cambio="Automático",
            combustivel="Diesel",
            passageiros=7,
        )

        self.assertContains(response, "SUV público de São Paulo")
        self.assertNotContains(response, "Hatch público de São Paulo")
        self.assertNotContains(response, "SUV público do Rio de Janeiro")
        self.assertNotContains(response, "Veículo pendente de aprovação")
        self.assertNotContains(response, "Veículo bloqueado")
        self.assertNotContains(response, "Veículo inativo")

    def test_sem_resultados(self):
        response = self.buscar(cidade="Curitiba")

        self.assertContains(response, "Nenhum veículo encontrado")
        self.assertContains(response, "0 veículos encontrados")

    def test_filtro_invalido_nao_quebra_a_pagina(self):
        response = self.buscar(passageiros="muitos")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível aplicar os filtros.")
        self.assertContains(response, 'id="erro-filtros"')
        self.assertContains(response, "Capacidade mínima (passageiros):")
        self.assertContains(response, "Corrija os filtros destacados acima")
        self.assertContains(response, "Nenhum veículo encontrado")

    def test_formulario_tem_estado_de_carregamento(self):
        response = self.buscar()

        for atributo in (
            "data-search-form",
            "data-search-submit",
            "data-search-spinner",
            "data-search-status",
        ):
            with self.subTest(atributo=atributo):
                self.assertContains(response, atributo)

    def test_pagina_fora_do_intervalo_exibe_404_amigavel(self):
        response = self.buscar(page=99)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertContains(
            response,
            "Ver veículos disponíveis",
            status_code=404,
        )

    def test_nao_expoe_dados_do_proprietario(self):
        response = self.buscar()

        self.assertNotContains(response, "proprietario-secreto")
        self.assertNotContains(response, "proprietario.secreto@example.com")
        self.assertNotContains(response, "Sensível")

    def test_nao_exibe_opcao_de_filtro_de_veiculo_nao_publico(self):
        response = self.buscar()

        self.assertNotContains(response, '<option value="Picape">')

    def test_pagina_resultados_em_seis_por_pagina(self):
        self.criar_veiculos_campinas(7)
        response = self.buscar(
            cidade="Campinas",
            diaria_min="100.00",
            diaria_max="200.00",
        )

        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(response.context["paginator"].per_page, 6)
        self.assertEqual(response.context["paginator"].count, 7)
        self.assertEqual(response.context["paginator"].num_pages, 2)
        self.assertEqual(len(response.context["veiculos"]), 6)
        self.assertContains(response, "Página 1 de 2")
        self.assertContains(response, "page=2")
        self.assertContains(response, "cidade=Campinas")
        self.assertContains(response, "diaria_min=100.00")
        self.assertContains(response, "diaria_max=200.00")
        self.assertContains(response, "Paginação 7")
        self.assertNotContains(response, "Paginação 1")

    def test_segunda_pagina_preserva_filtros(self):
        self.criar_veiculos_campinas(7)
        response = self.buscar(
            cidade="Campinas",
            categoria="Hatch",
            diaria_min="100.00",
            diaria_max="200.00",
            page=2,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["veiculos"]), 1)
        self.assertContains(response, "Página 2 de 2")
        self.assertContains(response, "Paginação 1")
        self.assertNotContains(response, "Paginação 7")
        self.assertContains(response, "page=1")
        self.assertContains(response, "cidade=Campinas")
        self.assertContains(response, "categoria=Hatch")
        self.assertContains(response, "diaria_min=100.00")
        self.assertContains(response, "diaria_max=200.00")

    def test_paginacao_ignora_veiculos_nao_publicos(self):
        self.criar_veiculos_campinas(7)
        Veiculo.objects.create(
            proprietario=self.proprietario,
            caracteristicas="Veículo oculto em Campinas",
            cidade="Campinas",
            categoria="Hatch",
            cambio="Manual",
            combustivel="Flex",
            passageiros=5,
            preco_diaria="150.00",
            ativo=True,
            bloqueado=False,
            aprovacao=Veiculo.Aprovacao.PENDENTE,
        )

        response = self.buscar(cidade="Campinas")
        segunda_pagina = self.buscar(cidade="Campinas", page=2)

        self.assertEqual(response.context["paginator"].count, 7)
        self.assertNotContains(response, "Veículo oculto em Campinas")
        self.assertNotContains(segunda_pagina, "Veículo oculto em Campinas")

    def test_sem_paginacao_quando_resultados_cabem_em_uma_pagina(self):
        response = self.buscar()

        self.assertFalse(response.context["is_paginated"])
        self.assertNotContains(
            response,
            'aria-label="Paginação dos resultados"',
        )

    def test_post_nao_e_permitido(self):
        response = self.client.post(reverse("core:resultados"))
        self.assertEqual(response.status_code, 405)

    def test_mantem_navegacao_e_indicacao_da_pagina_atual(self):
        response = self.buscar()

        self.assertTemplateUsed(response, "core/includes/navigation_links.html")
        self.assertContains(response, 'aria-label="Navegação principal"', count=1)
        self.assertContains(response, 'aria-label="Navegação mobile"', count=1)
        self.assertContains(
            response,
            f'href="{reverse("core:resultados")}" aria-current="page"',
            count=2,
        )


class DetalhesVeiculoTests(TestCase):
    """A página de detalhes deve exibir apenas o veículo público solicitado."""

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

        cls.hatch = criar_veiculo()
        cls.suv = criar_veiculo(
            cidade="Campinas",
            categoria="SUV",
            cambio="Automático",
            combustivel="Diesel",
            passageiros=7,
            preco_diaria="250.00",
        )
        cls.pendente = criar_veiculo(
            categoria="Picape",
            aprovacao=Veiculo.Aprovacao.PENDENTE,
        )
        cls.bloqueado = criar_veiculo(bloqueado=True)
        cls.inativo = criar_veiculo(ativo=False)

    def detalhe(self, pk):
        return self.client.get(reverse("core:detalhes", args=[pk]))

    def test_exibe_o_veiculo_publico_solicitado(self):
        response = self.detalhe(self.hatch.pk)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/detalhes.html")
        self.assertEqual(response.context["veiculo"], self.hatch)
        self.assertContains(response, "Hatch em São Paulo")
        self.assertContains(response, "Manual")
        self.assertContains(response, "Flex")
        self.assertContains(response, "5 lugares")
        self.assertContains(
            response,
            "Este anúncio está ativo, aprovado e visível publicamente.",
        )

    def test_exibe_caracteristicas_cadastradas(self):
        response = self.detalhe(self.hatch.pk)

        self.assertContains(response, "Sobre o carro")
        self.assertContains(response, "Veículo de teste")

    def test_exibe_diaria_cadastrada(self):
        response = self.detalhe(self.hatch.pk)

        self.assertContains(response, "R$ 150,00")
        self.assertContains(response, "Valor por dia definido no anúncio.")

    def test_sem_fotos_exibe_ilustracao(self):
        response = self.detalhe(self.hatch.pk)

        self.assertContains(response, "images/car.svg")
        self.assertNotContains(response, 'aria-label="Fotos do veículo"')

    def test_nao_expoe_dados_do_proprietario(self):
        response = self.detalhe(self.hatch.pk)

        self.assertNotContains(response, "proprietario-secreto")
        self.assertNotContains(response, "proprietario.secreto@example.com")
        self.assertNotContains(response, "Sensível")
        self.assertNotContains(response, "Rafael Costa")

    def test_veiculos_nao_publicos_retornam_404(self):
        for nome, veiculo in (
            ("pendente", self.pendente),
            ("bloqueado", self.bloqueado),
            ("inativo", self.inativo),
        ):
            with self.subTest(nome=nome):
                response = self.detalhe(veiculo.pk)
                self.assertEqual(response.status_code, 404)

    def test_veiculo_inexistente_retorna_404(self):
        response = self.detalhe(999999)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertContains(
            response,
            "Ver veículos disponíveis",
            status_code=404,
        )

    def test_link_da_busca_aponta_para_os_veiculos_corretos(self):
        response = self.client.get(reverse("core:resultados"))

        self.assertContains(
            response,
            f'href="{reverse("core:detalhes", args=[self.hatch.pk])}"',
        )
        self.assertContains(
            response,
            f'href="{reverse("core:detalhes", args=[self.suv.pk])}"',
        )
        self.assertNotContains(
            response,
            reverse("core:detalhes", args=[self.pendente.pk]),
        )
        self.assertNotContains(
            response,
            reverse("core:detalhes", args=[self.bloqueado.pk]),
        )
        self.assertNotContains(
            response,
            reverse("core:detalhes", args=[self.inativo.pk]),
        )

    def test_navegacao_da_busca_abre_o_veiculo_correto(self):
        href = reverse("core:detalhes", args=[self.hatch.pk])
        response = self.client.get(href)

        self.assertContains(response, "Hatch em São Paulo")
        self.assertNotContains(response, "SUV em Campinas")

    def test_indicacao_da_secao_resultados_na_navegacao(self):
        response = self.detalhe(self.hatch.pk)
        parser = NavigationParser()
        parser.feed(response.content.decode())

        for region in ("Navegação principal", "Navegação mobile"):
            with self.subTest(region=region):
                current = [
                    link for link in parser.links[region]
                    if "aria-current" in link
                ]
                self.assertEqual(len(current), 1)
                self.assertEqual(
                    current[0]["href"],
                    reverse("core:resultados"),
                )
                self.assertEqual(current[0]["aria-current"], "location")

    def test_volta_para_a_busca(self):
        response = self.detalhe(self.hatch.pk)

        self.assertContains(
            response,
            f'href="{reverse("core:resultados")}"',
        )

    def test_post_nao_e_permitido(self):
        response = self.client.post(
            reverse("core:detalhes", args=[self.hatch.pk]),
        )

        self.assertEqual(response.status_code, 405)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class DetalhesVeiculoFotosTests(TestCase):
    """As fotos cadastradas devem aparecer apenas no veículo correspondente."""

    @classmethod
    def setUpTestData(cls):
        cls.proprietario = Usuario.objects.create_user(
            username="proprietario-fotos",
            password="senha-de-teste",
            proprietario=True,
        )

        def criar_veiculo(cidade: str) -> Veiculo:
            return Veiculo.objects.create(
                proprietario=cls.proprietario,
                caracteristicas="Veículo com fotos",
                cidade=cidade,
                categoria="Hatch",
                cambio="Manual",
                combustivel="Flex",
                passageiros=5,
                preco_diaria="180.00",
                ativo=True,
                bloqueado=False,
                aprovacao=Veiculo.Aprovacao.APROVADO,
            )

        cls.veiculo = criar_veiculo("São Paulo")
        cls.outro_veiculo = criar_veiculo("Campinas")
        cls.foto_frente = FotoVeiculo.objects.create(
            veiculo=cls.veiculo,
            foto=SimpleUploadedFile(
                "frente.png", PNG_1X1, content_type="image/png",
            ),
        )
        cls.foto_lateral = FotoVeiculo.objects.create(
            veiculo=cls.veiculo,
            foto=SimpleUploadedFile(
                "lateral.png", PNG_1X1, content_type="image/png",
            ),
        )
        cls.foto_outro_veiculo = FotoVeiculo.objects.create(
            veiculo=cls.outro_veiculo,
            foto=SimpleUploadedFile(
                "outro.png", PNG_1X1, content_type="image/png",
            ),
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def detalhe(self, veiculo):
        return self.client.get(
            reverse("core:detalhes", args=[veiculo.pk]),
        )

    def test_exibe_fotos_cadastradas_na_ordem(self):
        response = self.detalhe(self.veiculo)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Fotos do veículo"')
        self.assertContains(response, self.foto_frente.foto.url)
        self.assertContains(response, self.foto_lateral.foto.url)
        html = response.content.decode()
        self.assertLess(
            html.index(self.foto_frente.foto.url),
            html.index(self.foto_lateral.foto.url),
        )

    def test_nao_exibe_fotos_de_outro_veiculo(self):
        response = self.detalhe(self.veiculo)

        self.assertNotContains(response, self.foto_outro_veiculo.foto.url)

    def test_com_fotos_nao_usa_ilustracao(self):
        response = self.detalhe(self.veiculo)

        self.assertNotContains(response, "images/car.svg")


class ResultadosSemVeiculosTests(TestCase):
    """O estado vazio deve distinguir ausência de anúncios de filtros sem resultado."""

    def buscar(self, **filtros):
        return self.client.get(reverse("core:resultados"), filtros)

    def test_sem_veiculos_e_sem_filtros(self):
        response = self.buscar()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0 veículos encontrados")
        self.assertContains(response, "Ainda não há veículos publicados")
        self.assertContains(response, "Voltar ao início")
        self.assertNotContains(response, "Nenhum veículo encontrado")

    def test_sem_veiculos_com_filtros(self):
        response = self.buscar(cidade="Curitiba")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0 veículos encontrados")
        self.assertContains(response, "Nenhum veículo encontrado")
        self.assertContains(response, "Limpar filtros")
        self.assertNotContains(response, "Ainda não há veículos publicados")


class AutenticacaoTests(TestCase):
    """O fluxo real de reserva exige login com as credenciais do Django."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="pessoa",
            email="pessoa@example.com",
            password="senha-de-teste",
        )

    def test_pagina_de_entrada_exibe_formulario_real(self):
        response = self.client.get(reverse("core:entrar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, "Entrar")
        self.assertNotContains(response, "Dados fictícios.")

    def test_login_valido_redireciona_para_minhas_reservas(self):
        response = self.client.post(
            reverse("core:entrar"),
            {"username": "PESSOA@example.com", "password": "senha-de-teste"},
        )

        self.assertRedirects(response, reverse("reservas:minhas"))
        self.assertEqual(
            self.client.session["_auth_user_id"],
            str(self.usuario.pk),
        )

    def test_login_respeita_o_next(self):
        destino = reverse("reservas:minhas")

        response = self.client.post(
            reverse("core:entrar"),
            {
                "username": "pessoa@example.com",
                "password": "senha-de-teste",
                "next": destino,
            },
        )

        self.assertRedirects(response, destino)

    def test_login_invalido_mostra_erro(self):
        response = self.client.post(
            reverse("core:entrar"),
            {"username": "pessoa@example.com", "password": "senha-errada"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail ou senha inválidos.")

    def test_navegacao_autenticada_oferece_sair(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "Sair")
        self.assertContains(response, reverse("core:sair"))
        self.assertNotContains(response, f'href="{reverse("core:entrar")}"')

    def test_logout_encerra_a_sessao(self):
        self.client.force_login(self.usuario)

        response = self.client.post(reverse("core:sair"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PwaTests(SimpleTestCase):
    """A PWA deve expor manifesto, service worker e tela offline."""

    def test_manifesto_disponivel(self):
        response = self.client.get(reverse("core:manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Type"],
            "application/manifest+json",
        )
        dados = response.json()
        self.assertEqual(dados["short_name"], "ShareCar")
        self.assertEqual(dados["lang"], "pt-BR")
        self.assertEqual(dados["display"], "standalone")
        self.assertEqual(dados["start_url"], reverse("core:home"))
        self.assertEqual(dados["theme_color"], "#0f766e")
        tamanhos = {icone["sizes"] for icone in dados["icons"]}
        self.assertIn("192x192", tamanhos)
        self.assertIn("512x512", tamanhos)
        self.assertTrue(
            any(icone["purpose"] == "maskable" for icone in dados["icons"])
        )
        for icone in dados["icons"]:
            self.assertEqual(icone["type"], "image/png")
            self.assertTrue(icone["src"].startswith("/static/icons/"))

    def test_service_worker_servido_na_raiz(self):
        response = self.client.get(reverse("core:service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Type"].split(";")[0],
            "application/javascript",
        )
        self.assertEqual(response.headers["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", response.headers["Cache-Control"])
        conteudo = response.content.decode()
        self.assertIn("sharecar-v1", conteudo)
        self.assertIn(reverse("core:offline"), conteudo)
        for caminho in (
            "css/base.css",
            "js/pwa.js",
            "icons/icon-192.png",
            "icons/maskable-512.png",
        ):
            with self.subTest(caminho=caminho):
                self.assertIn(static(caminho), conteudo)

    def test_tela_offline(self):
        response = self.client.get(reverse("core:offline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Você está offline")
        self.assertContains(response, "Tentar novamente")
        self.assertContains(response, 'rel="manifest"')

    def test_paginas_incluem_manifesto_e_registro(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, f'href="{reverse("core:manifest")}"')
        self.assertContains(
            response,
            f'data-sw-url="{reverse("core:service_worker")}"',
        )
        self.assertContains(response, "js/pwa.js")
        self.assertContains(response, "apple-touch-icon")
        self.assertContains(response, "apple-mobile-web-app-capable")
