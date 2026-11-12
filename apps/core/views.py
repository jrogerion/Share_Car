from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, ListView, TemplateView

from apps.avaliacoes.services import resumo_avaliacoes_veiculo
from apps.reservas.forms import ReservaForm
from apps.reservas.services import (
    ReservaInvalida, estimar_reserva, motivo_impedimento_locatario,
)
from apps.veiculos.consultas import (
    buscar_veiculos,
    com_fotos_ordenadas,
    veiculos_publicos,
)
from apps.veiculos.disponibilidade import motivo_indisponibilidade
from apps.veiculos.forms import BuscaVeiculoForm
from apps.veiculos.models import Veiculo


class HomeView(TemplateView):
    """Exibe a página inicial estática, sem consultas ou contexto dinâmico."""

    template_name = "core/home.html"


@method_decorator(never_cache, name="dispatch")
class DetalhesVeiculoView(DetailView):
    """Exibe um veículo público; veículos não públicos resultam em 404."""

    template_name = "core/detalhes.html"
    context_object_name = "veiculo"

    def get_queryset(self):
        return com_fotos_ordenadas(veiculos_publicos())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fotos"] = self.object.fotos.all()
        context["avaliacoes"] = resumo_avaliacoes_veiculo(self.object)
        context["eh_proprietario"] = (
            self.request.user.is_authenticated
            and self.object.proprietario_id == self.request.user.pk
        )

        tem_periodo = bool(
            self.request.GET.get("retirada")
            or self.request.GET.get("devolucao")
        )
        form = ReservaForm(self.request.GET if tem_periodo else None)
        context["periodo_form"] = form
        context["periodo_consultado"] = tem_periodo
        context["periodo_disponivel"] = False

        if tem_periodo and form.is_valid():
            inicio = form.cleaned_data["retirada"]
            fim = form.cleaned_data["devolucao"]
            motivo = motivo_indisponibilidade(self.object, inicio, fim)
            context["motivo_indisponibilidade"] = motivo
            context["periodo_disponivel"] = not motivo
            try:
                context["estimativa"] = estimar_reserva(self.object, inicio, fim)
            except ReservaInvalida as exc:
                context["periodo_disponivel"] = False
                context["motivo_indisponibilidade"] = str(exc)
            if self.request.user.is_authenticated:
                context["impedimento_locatario"] = motivo_impedimento_locatario(
                    self.request.user, fim,
                )
            context["periodo_inicio"] = inicio
            context["periodo_fim"] = fim

        return context


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
        return com_fotos_ordenadas(buscar_veiculos(
            cidade=dados.get("cidade", ""),
            categoria=dados.get("categoria", ""),
            cambio=dados.get("cambio", ""),
            combustivel=dados.get("combustivel", ""),
            passageiros_min=dados.get("passageiros"),
            diaria_min=dados.get("diaria_min"),
            diaria_max=dados.get("diaria_max"),
            inicio=dados.get("retirada"),
            fim=dados.get("devolucao"),
        ))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        valido = self.filtro.is_valid()
        dados = self.filtro.cleaned_data

        context["filtro"] = self.filtro
        context["total_veiculos"] = context["paginator"].count
        context["cidade_busca"] = dados.get("cidade", "")
        context["filtro_invalido"] = not valido
        context["busca_ativa"] = True if not valido else any(dados.values())
        return context
