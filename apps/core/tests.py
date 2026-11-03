from html.parser import HTMLParser

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.contas.models import Usuario
from apps.veiculos.models import Veiculo


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
        "home", "entrar", "detalhes", "resumo",
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

    def test_reservation_demo_flow(self):
        steps = (
            ("detalhes", "resumo"),
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
            "detalhes": "resultados", "resumo": "resultados",
            "pagamento": "resultados", "reservas": "reservas",
            "checkin": "reservas", "avaliacao": "reservas",
            "veiculo": "veiculo",
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
        self.assertContains(response, "Nenhum veículo encontrado")

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
