from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, ListView

from apps.avaliacoes.services import avaliacoes_da_reserva, pode_avaliar
from apps.locacoes.services import check_in_da_reserva, check_out_da_reserva
from apps.pagamentos.models import Pagamento
from apps.veiculos.consultas import veiculos_publicos
from apps.veiculos.disponibilidade import STATUS_RESERVA_BLOQUEANTES
from apps.veiculos.models import PeriodoAgenda, Veiculo

from .forms import PeriodoAgendaForm, ReservaForm
from .models import Reserva
from .services import (
    AgendaInvalida,
    ReservaInvalida,
    aceitar_reserva,
    adicionar_periodo_agenda,
    cancelar_reserva,
    criar_reserva,
    pagamento_aprovado,
    recusar_reserva,
    remover_periodo_agenda,
)


def _executar_acao(request, reserva, acao, mensagem):
    try:
        acao(reserva)
    except ReservaInvalida as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, mensagem)
    return redirect("reservas:detalhe", pk=reserva.pk)


class MinhasReservasView(LoginRequiredMixin, ListView):
    """Lista as reservas em que o usuário é locatário ou proprietário."""

    template_name = "reservas/minhas.html"
    context_object_name = "reservas"

    def get_queryset(self):
        usuario = self.request.user
        return (
            Reserva.objects.filter(
                Q(locatario=usuario) | Q(veiculo__proprietario=usuario)
            )
            .select_related("veiculo", "locatario", "veiculo__proprietario")
            .order_by("-id")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservas = self.get_queryset()
        context["como_locatario"] = reservas.filter(locatario=self.request.user)
        context["como_proprietario"] = reservas.filter(
            veiculo__proprietario=self.request.user
        )
        context["meus_veiculos"] = Veiculo.objects.filter(
            proprietario=self.request.user
        ).order_by("cidade", "categoria")
        return context


class DetalheReservaView(LoginRequiredMixin, DetailView):
    """Exibe a reserva apenas para o locatário ou o proprietário do veículo."""

    template_name = "reservas/detalhe.html"
    context_object_name = "reserva"

    def get_queryset(self):
        usuario = self.request.user
        return Reserva.objects.filter(
            Q(locatario=usuario) | Q(veiculo__proprietario=usuario)
        ).select_related("veiculo", "locatario", "veiculo__proprietario")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reserva = self.object
        usuario = self.request.user
        context["eh_locatario"] = reserva.locatario_id == usuario.pk
        context["eh_proprietario"] = reserva.veiculo.proprietario_id == usuario.pk
        context["pode_aceitar"] = (
            context["eh_proprietario"]
            and reserva.status == Reserva.Status.SOLICITADA
        )
        context["pode_recusar"] = context["pode_aceitar"]
        context["pode_cancelar"] = (
            context["eh_locatario"]
            and reserva.status
            in (Reserva.Status.SOLICITADA, Reserva.Status.ACEITA)
        )

        try:
            pagamento = reserva.pagamento
        except Pagamento.DoesNotExist:
            pagamento = None
        aprovado = pagamento_aprovado(reserva)
        check_in = check_in_da_reserva(reserva)
        check_out = check_out_da_reserva(reserva)

        context["pagamento"] = pagamento
        context["pagamento_aprovado"] = aprovado
        context["pode_pagar"] = (
            context["eh_locatario"]
            and reserva.status == Reserva.Status.ACEITA
            and not aprovado
        )
        context["check_in"] = check_in
        context["check_out"] = check_out
        context["pode_checkin"] = (
            context["eh_locatario"]
            and reserva.status == Reserva.Status.ACEITA
            and aprovado
            and check_in is None
        )
        context["pode_checkout"] = (
            context["eh_locatario"]
            and reserva.status == Reserva.Status.EM_ANDAMENTO
            and check_in is not None
            and check_out is None
        )

        avaliacoes = list(avaliacoes_da_reserva(reserva))
        minha_avaliacao = next(
            (item for item in avaliacoes if item.autor_id == usuario.pk),
            None,
        )
        outra_avaliacao = next(
            (item for item in avaliacoes if item.autor_id != usuario.pk),
            None,
        )
        context["minha_avaliacao"] = minha_avaliacao
        context["outra_parte_avaliou"] = outra_avaliacao is not None
        # A nota da outra parte só é liberada depois que ambas avaliarem.
        context["avaliacao_outra_parte"] = (
            outra_avaliacao
            if minha_avaliacao is not None and outra_avaliacao is not None
            else None
        )
        context["pode_avaliar"] = pode_avaliar(reserva, usuario)
        return context


class CriarReservaView(LoginRequiredMixin, View):
    """Cria uma solicitação de reserva para um veículo público."""

    def post(self, request, pk):
        veiculo = get_object_or_404(veiculos_publicos(), pk=pk)
        form = ReservaForm(request.POST)

        if not form.is_valid():
            messages.error(request, self._primeiro_erro(form))
            return self._voltar_ao_veiculo(veiculo, form.data)

        inicio = form.cleaned_data["retirada"]
        fim = form.cleaned_data["devolucao"]

        try:
            reserva = criar_reserva(
                veiculo=veiculo,
                locatario=request.user,
                inicio=inicio,
                fim=fim,
            )
        except ReservaInvalida as exc:
            messages.error(request, str(exc))
            return self._voltar_ao_veiculo(veiculo, form.data)
        except IntegrityError:
            messages.error(
                request,
                "O período acabou de ser reservado por outra pessoa. "
                "Escolha novas datas.",
            )
            return self._voltar_ao_veiculo(veiculo, form.data)

        messages.success(
            request,
            "Solicitação enviada. Aguarde o aceite do proprietário.",
        )
        return redirect("reservas:detalhe", pk=reserva.pk)

    @staticmethod
    def _primeiro_erro(form):
        for erros in form.errors.values():
            for erro in erros:
                return erro
        return "Revise o período informado."

    @staticmethod
    def _voltar_ao_veiculo(veiculo, dados):
        parametros = urlencode(
            {
                "retirada": dados.get("retirada", ""),
                "devolucao": dados.get("devolucao", ""),
            }
        )
        url = reverse("core:detalhes", args=[veiculo.pk])
        return redirect(f"{url}?{parametros}")


class AceitarReservaView(LoginRequiredMixin, View):
    """Permite ao proprietário aceitar uma solicitação pendente."""

    def post(self, request, pk):
        reserva = get_object_or_404(
            Reserva.objects.filter(veiculo__proprietario=request.user),
            pk=pk,
        )
        return _executar_acao(
            request,
            reserva,
            aceitar_reserva,
            "Reserva aceita.",
        )


class RecusarReservaView(LoginRequiredMixin, View):
    """Permite ao proprietário recusar uma solicitação pendente."""

    def post(self, request, pk):
        reserva = get_object_or_404(
            Reserva.objects.filter(veiculo__proprietario=request.user),
            pk=pk,
        )
        return _executar_acao(
            request,
            reserva,
            recusar_reserva,
            "Reserva recusada.",
        )


class CancelarReservaView(LoginRequiredMixin, View):
    """Permite ao locatário cancelar sua própria reserva."""

    def post(self, request, pk):
        reserva = get_object_or_404(
            Reserva.objects.filter(locatario=request.user),
            pk=pk,
        )
        return _executar_acao(
            request,
            reserva,
            cancelar_reserva,
            "Reserva cancelada.",
        )


@method_decorator(never_cache, name="dispatch")
class AgendaVeiculoView(LoginRequiredMixin, View):
    """Permite ao proprietário cadastrar disponibilidade e bloqueios."""

    template_name = "reservas/agenda.html"

    def get(self, request, pk):
        veiculo = self._veiculo_do_proprietario(request, pk)
        return self._renderizar(request, veiculo, PeriodoAgendaForm())

    def post(self, request, pk):
        veiculo = self._veiculo_do_proprietario(request, pk)
        form = PeriodoAgendaForm(request.POST)

        if form.is_valid():
            try:
                adicionar_periodo_agenda(
                    veiculo=veiculo, **form.cleaned_data,
                )
            except AgendaInvalida as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Período adicionado à agenda.")
                return redirect("reservas:agenda", pk=veiculo.pk)

        return self._renderizar(request, veiculo, form)

    def _renderizar(self, request, veiculo, form):
        periodos = veiculo.periodos_agenda.order_by("inicio", "id")
        pagina = Paginator(periodos, 20).get_page(request.GET.get("page"))
        ocupacoes = Reserva.objects.filter(
            veiculo=veiculo, status__in=STATUS_RESERVA_BLOQUEANTES,
            fim__gt=timezone.localdate(),
        ).order_by("inicio", "pk")[:10]
        return render(
            request,
            self.template_name,
            {
                "veiculo": veiculo, "form": form,
                "periodos": pagina.object_list, "page_obj": pagina,
                "reservas_vigentes": ocupacoes,
            },
        )

    @staticmethod
    def _veiculo_do_proprietario(request, pk):
        return get_object_or_404(
            Veiculo.objects.filter(proprietario=request.user),
            pk=pk,
        )


class RemoverPeriodoView(LoginRequiredMixin, View):
    """Remove um período da agenda do próprio veículo."""

    def post(self, request, pk):
        periodo = get_object_or_404(
            PeriodoAgenda.objects.filter(veiculo__proprietario=request.user),
            pk=pk,
        )
        veiculo_pk = periodo.veiculo_id
        try:
            remover_periodo_agenda(periodo)
        except AgendaInvalida as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Período removido da agenda.")
        return redirect("reservas:agenda", pk=veiculo_pk)
