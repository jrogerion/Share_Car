from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from apps.reservas.models import Reserva

from .forms import AvaliacaoForm
from .services import (
    AvaliacaoInvalida,
    avaliacoes_da_reserva,
    avaliar_reserva,
    participante_da_reserva,
    pode_avaliar,
)


@method_decorator(never_cache, name="dispatch")
class AvaliarReservaView(LoginRequiredMixin, View):
    """Permite que locatário e proprietário avaliem a locação concluída."""

    template_name = "avaliacoes/avaliar.html"

    def get(self, request, reserva_pk):
        reserva = self._reserva(request, reserva_pk)
        if not pode_avaliar(reserva, request.user):
            messages.error(
                request,
                "Esta reserva não está disponível para avaliação.",
            )
            return redirect("reservas:detalhe", pk=reserva.pk)

        return self._renderizar(request, reserva, AvaliacaoForm())

    def post(self, request, reserva_pk):
        reserva = self._reserva(request, reserva_pk)
        if not pode_avaliar(reserva, request.user):
            messages.error(
                request, "Esta reserva não está disponível para avaliação.",
            )
            return redirect("reservas:detalhe", pk=reserva.pk)
        form = AvaliacaoForm(request.POST)

        if not form.is_valid():
            return self._renderizar(request, reserva, form)

        try:
            avaliar_reserva(
                reserva=reserva,
                autor=request.user,
                nota=int(form.cleaned_data["nota"]),
            )
        except AvaliacaoInvalida as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Avaliação registrada. As notas ficam disponíveis quando "
                "ambas as partes avaliam.",
            )
        return redirect("reservas:detalhe", pk=reserva.pk)

    @staticmethod
    def _reserva(request, pk):
        usuario = request.user
        return get_object_or_404(
            Reserva.objects.filter(
                Q(locatario=usuario) | Q(veiculo__proprietario=usuario)
            ).select_related("veiculo", "veiculo__proprietario", "locatario"),
            pk=pk,
        )

    def _renderizar(self, request, reserva, form):
        avaliacoes = list(avaliacoes_da_reserva(reserva))
        minha = next(
            (item for item in avaliacoes if item.autor_id == request.user.pk),
            None,
        )
        outra = next(
            (item for item in avaliacoes if item.autor_id != request.user.pk),
            None,
        )
        return render(
            request,
            self.template_name,
            {
                "reserva": reserva,
                "form": form,
                "avaliado": participante_da_reserva(reserva, request.user),
                "minha_avaliacao": minha,
                "avaliacao_outra_parte": outra if minha is not None else None,
                "outra_parte_avaliou": outra is not None,
            },
        )
