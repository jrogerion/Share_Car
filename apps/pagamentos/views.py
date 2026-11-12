from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from apps.reservas.models import Reserva

from .forms import PagamentoForm
from .models import Pagamento
from .services import PagamentoInvalido, simular_pagamento


@method_decorator(never_cache, name="dispatch")
class PagarReservaView(LoginRequiredMixin, View):
    """Permite ao locatário simular o pagamento de uma reserva aceita."""

    template_name = "pagamentos/pagar.html"

    def get(self, request, reserva_pk):
        reserva = self._reserva(request, reserva_pk)
        bloqueio = self._bloqueio(reserva)
        if bloqueio:
            messages.error(request, bloqueio)
            return redirect("reservas:detalhe", pk=reserva.pk)

        return self._renderizar(request, reserva, PagamentoForm())

    def post(self, request, reserva_pk):
        reserva = self._reserva(request, reserva_pk)
        bloqueio = self._bloqueio(reserva)
        if bloqueio:
            messages.error(request, bloqueio)
            return redirect("reservas:detalhe", pk=reserva.pk)

        form = PagamentoForm(request.POST)
        if not form.is_valid():
            return self._renderizar(request, reserva, form)

        try:
            pagamento = simular_pagamento(
                reserva=reserva,
                meio=form.cleaned_data["meio"],
                resultado=form.cleaned_data["resultado"],
            )
        except PagamentoInvalido as exc:
            messages.error(request, str(exc))
        else:
            if pagamento.status == Pagamento.Status.APROVADO:
                messages.success(
                    request,
                    "Pagamento aprovado na simulação. O check-in está liberado.",
                )
            else:
                messages.warning(
                    request,
                    "Pagamento recusado na simulação. Você pode tentar novamente.",
                )
        return redirect("reservas:detalhe", pk=reserva.pk)

    @staticmethod
    def _reserva(request, pk):
        return get_object_or_404(
            Reserva.objects.filter(locatario=request.user).select_related(
                "veiculo", "veiculo__proprietario"
            ),
            pk=pk,
        )

    @staticmethod
    def _bloqueio(reserva):
        if reserva.status != Reserva.Status.ACEITA:
            return "O pagamento só está disponível para reservas aceitas."
        if Pagamento.objects.filter(
            reserva=reserva,
            status=Pagamento.Status.APROVADO,
        ).exists():
            return "Esta reserva já possui pagamento aprovado."
        return ""

    def _renderizar(self, request, reserva, form):
        try:
            pagamento = reserva.pagamento
        except Pagamento.DoesNotExist:
            pagamento = None

        return render(
            request,
            self.template_name,
            {"reserva": reserva, "form": form, "pagamento": pagamento},
        )
