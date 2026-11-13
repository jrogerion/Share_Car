from django.test import SimpleTestCase
from django.urls import reverse


class ComoFuncionaPageTests(SimpleTestCase):
    """A página pública deve apresentar o guia e ser alcançável pelo footer."""

    def test_pagina_renderiza_sem_autenticacao(self):
        response = self.client.get(reverse("core:como_funciona"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/como_funciona.html")
        self.assertContains(response, "Como funciona o ShareCar")
        self.assertContains(response, 'id="conteudo"')

    def test_footer_aponta_para_a_pagina(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(
            response,
            f'href="{reverse("core:como_funciona")}">Como funciona</a>',
        )

    def test_pagina_reune_os_fluxos_reais_da_plataforma(self):
        response = self.client.get(reverse("core:como_funciona"))

        for url in (
            reverse("core:resultados"),
            reverse("core:entrar"),
            reverse("contas:cadastro"),
            reverse("contas:perfil"),
            reverse("reservas:minhas"),
            reverse("veiculos:meus"),
            reverse("core:veiculo"),
        ):
            with self.subTest(url=url):
                self.assertContains(response, f'href="{url}"')

        for conteudo in (
            "CNH", "check-in", "check-out", "pagamento simulado",
            "avaliações", "agenda", "comissão",
        ):
            with self.subTest(conteudo=conteudo):
                self.assertContains(response, conteudo)

    def test_navegacao_principal_e_mobile_preservadas(self):
        response = self.client.get(reverse("core:como_funciona"))

        self.assertContains(response, 'aria-label="Navegação principal"', count=1)
        self.assertContains(response, 'aria-label="Navegação mobile"', count=1)

    def test_pagina_nao_aceita_post(self):
        response = self.client.post(reverse("core:como_funciona"))

        self.assertEqual(response.status_code, 405)
