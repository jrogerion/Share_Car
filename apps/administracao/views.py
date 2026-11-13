from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, TemplateView

from apps.contas.models import Usuario
from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo
from apps.veiculos.consultas import com_fotos_ordenadas

from .forms import ConfiguracaoComissaoForm
from .models import ConfiguracaoComissao

DECISOES = {"aprovar", "rejeitar"}


class AdministradorMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a área administrativa a usuários staff."""

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Acesso restrito à administração.")
            return redirect("contas:painel")
        return super().handle_no_permission()


@method_decorator(never_cache, name="dispatch")
class PainelAdministrativoView(AdministradorMixin, TemplateView):
    """Resume aprovações, bloqueios, pagamentos e reservas recentes."""

    template_name = "administracao/painel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        documentos_pendentes = Usuario.objects.filter(
            aprovacao_documento=Usuario.Aprovacao.PENDENTE,
        ).exclude(documento_identidade="")
        cnhs_pendentes = Usuario.objects.filter(
            aprovacao_cnh=Usuario.Aprovacao.PENDENTE,
        ).exclude(cnh_numero="")

        context["documentos_pendentes"] = documentos_pendentes.order_by(
            "username"
        )[:10]
        context["cnhs_pendentes"] = cnhs_pendentes.order_by("username")[:10]
        context["veiculos_pendentes"] = Veiculo.objects.filter(
            aprovacao=Veiculo.Aprovacao.PENDENTE
        ).select_related("proprietario").order_by("id")[:10]
        context["usuarios_recentes"] = Usuario.objects.order_by("-id")[:10]
        context["veiculos_recentes"] = Veiculo.objects.select_related(
            "proprietario"
        ).order_by("-id")[:10]
        context["reservas_recentes"] = Reserva.objects.select_related(
            "veiculo", "locatario"
        ).order_by("-id")[:10]
        context["pagamentos_recentes"] = Pagamento.objects.select_related(
            "reserva", "reserva__veiculo"
        ).order_by("-id")[:10]

        context["indicadores"] = {
            "usuarios": Usuario.objects.count(),
            "usuarios_pendentes": documentos_pendentes.count()
            + cnhs_pendentes.count(),
            "veiculos_pendentes": Veiculo.objects.filter(
                aprovacao=Veiculo.Aprovacao.PENDENTE
            ).count(),
            "veiculos_bloqueados": Veiculo.objects.filter(bloqueado=True).count(),
            "reservas_ativas": Reserva.objects.filter(
                status__in=[
                    Reserva.Status.ACEITA,
                    Reserva.Status.EM_ANDAMENTO,
                ]
            ).count(),
            "pagamentos_aprovados": Pagamento.objects.filter(
                status=Pagamento.Status.APROVADO
            ).count(),
        }
        return context


class AnalistaMixin(AdministradorMixin):
    """Mantém a mesma restrição de análise do Django Admin."""

    def test_func(self):
        return super().test_func() and self.request.user.is_superuser


def registrar_analise(request, objeto, campo):
    LogEntry.objects.log_actions(
        user_id=request.user.pk, queryset=[objeto], action_flag=CHANGE,
        change_message=[{"changed": {"fields": [campo]}}],
    )


class DecidirDocumentoView(AnalistaMixin, View):
    """Aprova ou rejeita o documento de identidade de um usuário."""

    @transaction.atomic
    def post(self, request, pk, decisao):
        if decisao not in DECISOES:
            messages.error(request, "Ação inválida.")
            return redirect("administracao:painel")

        usuario = get_object_or_404(Usuario.objects.select_for_update(), pk=pk)
        documento = usuario.documento_identidade
        if decisao == "aprovar" and (
            not documento or not documento.storage.exists(documento.name)
        ):
            messages.error(request, "O usuário ainda não enviou o documento.")
        else:
            usuario.aprovacao_documento = (
                Usuario.Aprovacao.APROVADO
                if decisao == "aprovar"
                else Usuario.Aprovacao.REJEITADO
            )
            usuario.save(update_fields=["aprovacao_documento"])
            registrar_analise(request, usuario, "aprovacao_documento")
            messages.success(
                request,
                f"Documento de {usuario.username} "
                f"{'aprovado' if decisao == 'aprovar' else 'rejeitado'}.",
            )
        return redirect("administracao:painel")


class DecidirCNHView(AnalistaMixin, View):
    """Aprova ou rejeita a CNH de um usuário."""

    @transaction.atomic
    def post(self, request, pk, decisao):
        if decisao not in DECISOES:
            messages.error(request, "Ação inválida.")
            return redirect("administracao:painel")

        usuario = get_object_or_404(Usuario.objects.select_for_update(), pk=pk)
        if decisao == "aprovar" and not (
            usuario.cnh_numero.strip() and usuario.cnh_validade
        ):
            messages.error(request, "O usuário ainda não informou a CNH completa.")
        elif (decisao == "aprovar" and
              usuario.cnh_validade < timezone.localdate()):
            messages.error(request, "Não é possível aprovar uma CNH vencida.")
        else:
            usuario.aprovacao_cnh = (
                Usuario.Aprovacao.APROVADO
                if decisao == "aprovar"
                else Usuario.Aprovacao.REJEITADO
            )
            usuario.save(update_fields=["aprovacao_cnh"])
            registrar_analise(request, usuario, "aprovacao_cnh")
            messages.success(
                request,
                f"CNH de {usuario.username} "
                f"{'aprovada' if decisao == 'aprovar' else 'rejeitada'}.",
            )
        return redirect("administracao:painel")


class AlternarBloqueioUsuarioView(AdministradorMixin, View):
    """Bloqueia ou reativa a conta de um usuário."""

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        if usuario.pk == request.user.pk:
            messages.error(request, "Você não pode bloquear a própria conta.")
        elif usuario.is_superuser and usuario.is_active:
            messages.error(request, "Não é permitido bloquear um superusuário.")
        else:
            usuario.is_active = not usuario.is_active
            usuario.save(update_fields=["is_active"])
            messages.success(
                request,
                f"Conta de {usuario.username} "
                f"{'reativada' if usuario.is_active else 'bloqueada'}.",
            )
        return redirect("administracao:painel")


@method_decorator(never_cache, name="dispatch")
class AnaliseVeiculoView(AdministradorMixin, DetailView):
    template_name = "administracao/veiculo.html"
    context_object_name = "veiculo"

    def get_queryset(self):
        return com_fotos_ordenadas(
            Veiculo.objects.select_related("proprietario"),
        )


class DecidirVeiculoView(AdministradorMixin, View):
    """Aprova ou rejeita um veículo anunciado."""

    @transaction.atomic
    def post(self, request, pk, decisao):
        if decisao not in DECISOES:
            messages.error(request, "Ação inválida.")
            return redirect("administracao:painel")

        veiculo = get_object_or_404(Veiculo.objects.select_for_update(), pk=pk)
        veiculo.aprovacao = (
            Veiculo.Aprovacao.APROVADO
            if decisao == "aprovar"
            else Veiculo.Aprovacao.REJEITADO
        )
        veiculo.save(update_fields=["aprovacao"])
        registrar_analise(request, veiculo, "aprovacao")
        messages.success(
            request,
            f"Veículo #{veiculo.pk} "
            f"{'aprovado' if decisao == 'aprovar' else 'rejeitado'}.",
        )
        return redirect("administracao:painel")


class AlternarBloqueioVeiculoView(AdministradorMixin, View):
    """Bloqueia ou desbloqueia um veículo."""

    @transaction.atomic
    def post(self, request, pk):
        veiculo = get_object_or_404(Veiculo.objects.select_for_update(), pk=pk)
        veiculo.bloqueado = not veiculo.bloqueado
        veiculo.save(update_fields=["bloqueado"])
        registrar_analise(request, veiculo, "bloqueado")
        messages.success(
            request,
            f"Veículo #{veiculo.pk} "
            f"{'bloqueado' if veiculo.bloqueado else 'desbloqueado'}.",
        )
        return redirect("administracao:painel")


class ConfiguracaoComissaoView(AdministradorMixin, View):
    """Permite ajustar o percentual de comissão das novas reservas."""

    template_name = "administracao/comissao.html"

    def get(self, request):
        configuracao, _ = ConfiguracaoComissao.objects.get_or_create(
            pk=1,
            defaults={"percentual": "15.00"},
        )
        form = ConfiguracaoComissaoForm(instance=configuracao)
        return render(
            request,
            self.template_name,
            {"form": form, "configuracao": configuracao},
        )

    def post(self, request):
        configuracao, _ = ConfiguracaoComissao.objects.get_or_create(
            pk=1,
            defaults={"percentual": "15.00"},
        )
        form = ConfiguracaoComissaoForm(request.POST, instance=configuracao)
        if form.is_valid():
            form.save()
            messages.success(request, "Comissão atualizada para novas reservas.")
            return redirect("administracao:painel")
        return render(
            request,
            self.template_name,
            {"form": form, "configuracao": configuracao},
        )
