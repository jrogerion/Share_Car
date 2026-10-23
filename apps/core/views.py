from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Exibe a página inicial estática, sem consultas ou contexto dinâmico."""

    template_name = "core/home.html"
