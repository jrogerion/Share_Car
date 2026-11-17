from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, ListView

from apps.avaliacoes.services import avaliacoes_da_reserva, pode_avaliar
from apps.contas.mixins import ContaPessoalMixin
from apps.locacoes.services import check_in_da_reserva, check_out_da_reserva
from apps.pagamentos.models import Pagamento
from apps.veiculos.consultas import veiculos_publicos
from apps.veiculos.disponibilidade import STATUS_RESERVA_BLOQUEANTES
from apps.veiculos.models import FotoVeiculo, PeriodoAgenda, Veiculo

from .forms import PeriodoAgendaForm, ReservaForm
from .models import Reserva
from .services import (
    AgendaInvalida,
    ReservaInvalida,
    aceitar_reserva,
    adicionar_periodo_agenda,
    cancelar_reserva,
    criar_reserva,
    motivo_impedimento_aceite,
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


@method_decorator(never_cache, name="dispatch")
class MinhasReservasView(ContaPessoalMixin, LoginRequiredMixin, ListView):
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
        reservas = self.object_list
        status_ativos = (
            Reserva.Status.SOLICITADA, Reserva.Status.ACEITA,
            Reserva.Status.EM_ANDAMENTO,
        )
        status_historico = (
            Reserva.Status.CONCLUIDA, Reserva.Status.CANCELADA,
            Reserva.Status.RECUSADA,
        )
        historico = self.request.GET.get("situacao") == "historico"
        context["historico"] = historico
        context.update(reservas.aggregate(
            total_ativas=Count("pk", filter=Q(status__in=status_ativos)),
            total_historico=Count("pk", filter=Q(status__in=status_historico)),
        ))
        reservas = reservas.filter(
            status__in=status_historico if historico else status_ativos,
        ).prefetch_related(
            Prefetch("veiculo__fotos", queryset=FotoVeiculo.objects.order_by("id")),
        )
        locatario = Paginator(reservas.filter(locatario=self.request.user), 10)
        proprietario = Paginator(reservas.filter(
            veiculo__proprietario=self.request.user,
        ), 10)
        context["pagina_locatario"] = locatario.get_page(
            self.request.GET.get("locatario_page"),
        )
        context["pagina_proprietario"] = proprietario.get_page(
            self.request.GET.get("proprietario_page"),
        )
        context["como_locatario"] = context["pagina_locatario"].object_list
        context["como_proprietario"] = (
            context["pagina_proprietario"].object_list
        )
        meus_veiculos = Veiculo.objects.filter(
            proprietario=self.request.user
        ).order_by("cidade", "categoria")
        context["pagina_veiculos"] = Paginator(meus_veiculos, 10).get_page(
            self.request.GET.get("veiculos_page"),
        )
        context["meus_veiculos"] = context["pagina_veiculos"].object_list
        return context


@method_decorator(never_cache, name="dispatch")
class DetalheReservaView(ContaPessoalMixin, LoginRequiredMixin, DetailView):
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
        if context["pode_aceitar"]:
            impedimento = motivo_impedimento_aceite(reserva)
            context["impedimento_aceite"] = impedimento
            context["pode_aceitar"] = not impedimento
        context["pode_cancelar"] = (
            context["eh_locatario"]
            and reserva.status
            in (Reserva.Status.SOLICITADA, Reserva.Status.ACEITA)
        )

        try:
            pagamento = reserva.pagamento
        except Pagamento.DoesNotExist:
            pagamento = None
        aprovado = (
            pagamento is not None
            and pagamento.status == Pagamento.Status.APROVADO
        )
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
        encerrada = reserva.status in (
            Reserva.Status.CANCELADA, Reserva.Status.RECUSADA,
        )
        etapa = 1
        if reserva.status == Reserva.Status.ACEITA:
            etapa = 3 if aprovado else 2
        elif reserva.status == Reserva.Status.EM_ANDAMENTO:
            etapa = 4
        elif reserva.status == Reserva.Status.CONCLUIDA:
            etapa = 5
        context["jornada_encerrada"] = encerrada
        context["etapas_reserva"] = [
            {
                "nome": nome,
                "concluida": not encerrada and indice < etapa,
                "atual": not encerrada and indice == etapa,
            }
            for indice, nome in enumerate(
                ("Solicitação", "Aceite", "Pagamento", "Retirada", "Devolução"),
            )
        ]
        if encerrada:
            orientacao = "Esta reserva foi encerrada. Consulte os valores e o pagamento abaixo."
        elif context["pode_aceitar"]:
            orientacao = "Analise o período e os valores para aceitar ou recusar a solicitação."
        elif reserva.status == Reserva.Status.SOLICITADA:
            orientacao = "A solicitação aguarda a análise do proprietário."
        elif context["pode_pagar"]:
            orientacao = "A reserva foi aceita. Simule o pagamento para liberar a retirada."
        elif context["pode_checkin"]:
            orientacao = "Pagamento aprovado. Registre a vistoria de retirada para iniciar a locação."
        elif context["pode_checkout"]:
            orientacao = "A locação está em andamento. Registre a vistoria de devolução ao finalizar."
        elif context["pode_avaliar"]:
            orientacao = "Locação concluída. Conte como foi sua experiência na avaliação."
        elif reserva.status == Reserva.Status.CONCLUIDA:
            orientacao = "Locação concluída. Os registros e valores estão disponíveis abaixo."
        elif reserva.status == Reserva.Status.EM_ANDAMENTO:
            orientacao = "A locação está em andamento. Aguarde o registro da devolução pelo locatário."
        elif aprovado:
            orientacao = "Pagamento aprovado. Aguarde a vistoria de retirada pelo locatário."
        else:
            orientacao = "A reserva foi aceita. Aguarde o pagamento do locatário."
        context["orientacao_etapa"] = orientacao
        return context


class CriarReservaView(ContaPessoalMixin, LoginRequiredMixin, View):
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
        except IntegrityError as exc:
            diagnostico = getattr(exc.__cause__, "diag", None)
            if (
                getattr(diagnostico, "constraint_name", None)
                != "reserva_sem_sobreposicao"
            ):
                raise
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
        if not veiculos_publicos().filter(pk=veiculo.pk).exists():
            return redirect("core:resultados")
        parametros = urlencode(
            {
                "retirada": dados.get("retirada", ""),
                "devolucao": dados.get("devolucao", ""),
            }
        )
        url = reverse("core:detalhes", args=[veiculo.pk])
        return redirect(f"{url}?{parametros}")


class AceitarReservaView(ContaPessoalMixin, LoginRequiredMixin, View):
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


class RecusarReservaView(ContaPessoalMixin, LoginRequiredMixin, View):
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


class CancelarReservaView(ContaPessoalMixin, LoginRequiredMixin, View):
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
class AgendaVeiculoView(ContaPessoalMixin, LoginRequiredMixin, View):
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


class RemoverPeriodoView(ContaPessoalMixin, LoginRequiredMixin, View):
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
