from django.views.generic import ListView, TemplateView

from apps.veiculos.consultas import buscar_veiculos
from apps.veiculos.forms import BuscaVeiculoForm
from apps.veiculos.models import Veiculo


class HomeView(TemplateView):
    """Exibe a página inicial estática, sem consultas ou contexto dinâmico."""

    template_name = "core/home.html"


class ResultadosView(ListView):
    """Lista veículos públicos, aplicando os filtros informados na busca."""

    template_name = "core/resultados.html"
    context_object_name = "veiculos"
    paginate_by = 6

    def get_queryset(self):
        self.filtro = BuscaVeiculoForm(self.request.GET)
        if not self.filtro.is_valid():
            return Veiculo.objects.none()

        dados = self.filtro.cleaned_data
        return buscar_veiculos(
            cidade=dados.get("cidade", ""),
            categoria=dados.get("categoria", ""),
            cambio=dados.get("cambio", ""),
            combustivel=dados.get("combustivel", ""),
            passageiros_min=dados.get("passageiros"),
            diaria_min=dados.get("diaria_min"),
            diaria_max=dados.get("diaria_max"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtro"] = self.filtro
        context["total_veiculos"] = context["paginator"].count
        context["cidade_busca"] = (
            self.filtro.cleaned_data.get("cidade", "")
            if self.filtro.is_valid()
            else ""
        )
        return context
