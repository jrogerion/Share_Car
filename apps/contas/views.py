from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView, UpdateView

from .forms import (
    CadastroUsuarioForm, DocumentoIdentidadeForm, LoginEmailForm,
    PerfilUsuarioForm,
)

from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .models import Usuario


class LoginEmailView(LoginView):
    template_name = "core/entrar.html"
    authentication_form = LoginEmailForm


class SairView(LogoutView):
    next_page = reverse_lazy("core:entrar")

@method_decorator(never_cache, name="dispatch")
class EnviarDocumentoView(LoginRequiredMixin, FormView):
    template_name = "contas/documento.html"
    form_class = DocumentoIdentidadeForm
    success_url = reverse_lazy("contas:perfil")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request, "Documento enviado. Aprovação pendente.",
        )
        return super().form_valid(form)


@method_decorator(never_cache, name="dispatch")
class DocumentoIdentidadeView(LoginRequiredMixin, View):
    def get(self, request, pk):
        queryset = Usuario.objects.all()
        if not request.user.is_superuser:
            queryset = queryset.filter(pk=request.user.pk)
        usuario = queryset.filter(pk=pk).first()
        if not usuario or not usuario.documento_identidade:
            raise Http404("Documento não encontrado.")
        try:
            arquivo = usuario.documento_identidade.open("rb")
        except FileNotFoundError:
            raise Http404("Documento não encontrado.") from None
        # O download não executa conteúdo enviado pelo usuário no navegador.
        extensao = usuario.documento_identidade.name.rsplit(".", 1)[-1].lower()
        if extensao not in ("jpg", "jpeg", "png"):
            extensao = "bin"
        response = FileResponse(
            arquivo, as_attachment=True,
            filename=f"documento-identidade.{extensao}",
            content_type="application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response


@method_decorator(never_cache, name="dispatch")
class PerfilUsuarioView(LoginRequiredMixin, UpdateView):
    form_class = PerfilUsuarioForm
    template_name = "contas/perfil.html"
    success_url = reverse_lazy("contas:perfil")

    def get_object(self, queryset=None):
        return Usuario.objects.get(pk=self.request.user.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        validade = self.object.cnh_validade
        context["cnh_vencida"] = bool(
            validade and validade < timezone.localdate(),
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Perfil atualizado com sucesso.")
        return response


class CadastroUsuarioView(FormView):
    template_name = "contas/cadastro.html"
    form_class = CadastroUsuarioForm
    success_url = reverse_lazy("contas:cadastro_concluido")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("contas:painel")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            if not Usuario.objects.filter(
                email__iexact=form.cleaned_data["email"],
            ).exists():
                raise
            form.add_error("email", "Não é possível cadastrar este e-mail.")
            return self.form_invalid(form)
        return HttpResponseRedirect(self.get_success_url())


class CadastroConcluidoView(TemplateView):
    template_name = "contas/cadastro_concluido.html"


@method_decorator(never_cache, name="dispatch")
class PainelView(LoginRequiredMixin, TemplateView):
    """Resume a atividade do usuário como locatário e/ou proprietário."""

    template_name = "contas/painel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        hoje = timezone.localdate()

        reservas_locatario = Reserva.objects.filter(locatario=usuario)
        context["resumo_locatario"] = reservas_locatario.aggregate(
            total=Count("pk"),
            solicitadas=Count(
                "pk", filter=Q(status=Reserva.Status.SOLICITADA)
            ),
            ativas=Count(
                "pk",
                filter=Q(
                    status__in=[
                        Reserva.Status.ACEITA,
                        Reserva.Status.EM_ANDAMENTO,
                    ]
                ),
            ),
            concluidas=Count(
                "pk", filter=Q(status=Reserva.Status.CONCLUIDA)
            ),
        )
        context["proximas_locatario"] = list(
            reservas_locatario.filter(
                status__in=[
                    Reserva.Status.ACEITA,
                    Reserva.Status.EM_ANDAMENTO,
                ],
                fim__gte=hoje,
            )
            .select_related("veiculo")
            .order_by("inicio", "pk")[:3]
        )

        reservas_recebidas = Reserva.objects.filter(
            veiculo__proprietario=usuario
        )
        context["resumo_proprietario"] = reservas_recebidas.aggregate(
            quantidade=Count("pk"),
            pendentes=Count(
                "pk", filter=Q(status=Reserva.Status.SOLICITADA)
            ),
            ativas=Count(
                "pk",
                filter=Q(
                    status__in=[
                        Reserva.Status.ACEITA,
                        Reserva.Status.EM_ANDAMENTO,
                    ]
                ),
            ),
            concluidas=Count(
                "pk", filter=Q(status=Reserva.Status.CONCLUIDA)
            ),
            valor_contratado=Sum(
                "total",
                filter=Q(
                    status__in=[
                        Reserva.Status.ACEITA,
                        Reserva.Status.EM_ANDAMENTO,
                        Reserva.Status.CONCLUIDA,
                    ]
                ),
                default=Decimal("0.00"),
            ),
        )
        context["proximas_proprietario"] = list(
            reservas_recebidas.filter(
                status__in=[
                    Reserva.Status.ACEITA,
                    Reserva.Status.EM_ANDAMENTO,
                ],
                fim__gte=hoje,
            )
            .select_related("veiculo", "locatario")
            .order_by("inicio", "pk")[:3]
        )
        context["solicitacoes_pendentes"] = list(
            reservas_recebidas.filter(status=Reserva.Status.SOLICITADA)
            .select_related("veiculo", "locatario")
            .order_by("inicio", "pk")[:5]
        )

        meus_veiculos = Veiculo.objects.filter(proprietario=usuario)
        context["resumo_veiculos"] = meus_veiculos.aggregate(
            total=Count("pk"),
            publicados=Count(
                "pk",
                filter=Q(
                    ativo=True,
                    aprovacao=Veiculo.Aprovacao.APROVADO,
                    bloqueado=False,
                ),
            ),
            pendentes=Count(
                "pk",
                filter=Q(aprovacao=Veiculo.Aprovacao.PENDENTE),
            ),
            bloqueados=Count("pk", filter=Q(bloqueado=True)),
        )

        context["perfil_completo"] = bool(
            usuario.cnh_numero
            and usuario.cnh_validade
            and usuario.documento_identidade
        )
        return context
