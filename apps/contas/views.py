from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, TemplateView, UpdateView

from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .forms import CadastroForm, PerfilForm
from .models import Usuario


class CadastroView(CreateView):
    """Cria a conta, autentica o usuário e abre o painel."""

    model = Usuario
    form_class = CadastroForm
    template_name = "contas/cadastro.html"
    success_url = reverse_lazy("contas:painel")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("contas:painel")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        resposta = super().form_valid(form)
        login(self.request, self.object)
        messages.success(
            self.request,
            "Conta criada com sucesso. Complete seu perfil para começar.",
        )
        return resposta


class PerfilView(LoginRequiredMixin, UpdateView):
    """Permite que o usuário atualize os próprios dados e documentos."""

    model = Usuario
    form_class = PerfilForm
    template_name = "contas/perfil.html"
    success_url = reverse_lazy("contas:perfil")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Perfil atualizado.")
        return super().form_valid(form)


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
