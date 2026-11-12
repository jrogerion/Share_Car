from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from apps.reservas.models import Reserva

from .forms import RegistroLocacaoForm
from .models import RegistroLocacao
from .services import (
    LocacaoInvalida,
    check_in_da_reserva,
    check_out_da_reserva,
    motivo_impedimento_registro,
    registrar_locacao,
)


@method_decorator(never_cache, name="dispatch")
class RegistrarLocacaoView(LoginRequiredMixin, View):
    """Permite ao locatário registrar o check-in ou o check-out."""

    template_name = "locacoes/registrar.html"

    def get(self, request, reserva_pk, tipo):
        reserva = self._reserva(request, reserva_pk)
        bloqueio = motivo_impedimento_registro(reserva, tipo)
        if bloqueio:
            messages.error(request, bloqueio)
            return redirect("reservas:detalhe", pk=reserva.pk)
        return self._renderizar(
            request, reserva, tipo, RegistroLocacaoForm(tipo=tipo),
        )

    def post(self, request, reserva_pk, tipo):
        reserva = self._reserva(request, reserva_pk)
        bloqueio = motivo_impedimento_registro(reserva, tipo)
        if bloqueio:
            messages.error(request, bloqueio)
            return redirect("reservas:detalhe", pk=reserva.pk)
        form = RegistroLocacaoForm(request.POST, request.FILES, tipo=tipo)

        if not form.is_valid():
            return self._renderizar(request, reserva, tipo, form)

        try:
            registrar_locacao(
                reserva=reserva,
                tipo=tipo,
                quilometragem=form.cleaned_data["quilometragem"],
                nivel_combustivel=form.cleaned_data["nivel_combustivel"],
                fotos=form.cleaned_data["fotos"],
            )
        except LocacaoInvalida as exc:
            form.add_error(None, str(exc))
            return self._renderizar(request, reserva, tipo, form)

        mensagem = (
            "Check-in registrado. A locação está em andamento."
            if tipo == RegistroLocacao.Tipo.CHECK_IN
            else "Check-out registrado. A locação foi concluída."
        )
        messages.success(request, mensagem)
        return redirect("reservas:detalhe", pk=reserva.pk)

    @staticmethod
    def _reserva(request, pk):
        return get_object_or_404(
            Reserva.objects.filter(locatario=request.user).select_related(
                "veiculo"
            ),
            pk=pk,
        )

    def _renderizar(self, request, reserva, tipo, form):
        return render(
            request,
            self.template_name,
            {
                "reserva": reserva,
                "tipo": tipo,
                "eh_check_out": tipo == RegistroLocacao.Tipo.CHECK_OUT,
                "check_in": check_in_da_reserva(reserva),
                "check_out": check_out_da_reserva(reserva),
                "form": form,
            },
        )
