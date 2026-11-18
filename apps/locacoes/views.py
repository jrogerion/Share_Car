from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.utils.cache import patch_vary_headers

from apps.reservas.models import Reserva
from apps.contas.mixins import ContaPessoalMixin

from .forms import RegistroLocacaoForm
from .models import FotoRegistroLocacao, RegistroLocacao
from .services import (
    LocacaoInvalida,
    check_in_da_reserva,
    check_out_da_reserva,
    motivo_impedimento_registro,
    registrar_locacao,
)


@method_decorator(never_cache, name="dispatch")
class FotoVistoriaView(LoginRequiredMixin, View):
    """Entrega a foto somente aos participantes da reserva e à administração."""

    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        fotos = FotoRegistroLocacao.objects.all()
        if not request.user.conta_administrativa:
            fotos = fotos.filter(
                Q(registro__reserva__locatario=request.user)
                | Q(registro__reserva__veiculo__proprietario=request.user),
            )
        foto = get_object_or_404(fotos, pk=pk)
        extensao = foto.foto.name.rsplit(".", 1)[-1].lower()
        tipos = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
        if extensao not in tipos:
            raise Http404("Foto não encontrada.")
        try:
            arquivo = foto.foto.open("rb")
        except (OSError, ValueError):
            raise Http404("Foto não encontrada.") from None
        response = FileResponse(
            arquivo, content_type=tipos[extensao],
            as_attachment=request.GET.get("download") == "1",
            filename=f"vistoria-{foto.pk}.{extensao}",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cross-Origin-Resource-Policy"] = "same-origin"
        response["Referrer-Policy"] = "no-referrer"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        patch_vary_headers(response, ("Cookie",))
        return response


@method_decorator(never_cache, name="dispatch")
class RegistrarLocacaoView(ContaPessoalMixin, LoginRequiredMixin, View):
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
