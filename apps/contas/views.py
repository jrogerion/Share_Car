from decimal import Decimal
from smtplib import SMTPException

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.cache import patch_vary_headers
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, TemplateView, UpdateView

from .forms import (
    AlterarEmailForm, CadastroUsuarioForm, DocumentoIdentidadeForm, LoginEmailForm,
    PerfilUsuarioForm,
)

from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .models import Usuario
from .mixins import ContaPessoalMixin
from .services import (
    confirmar_alteracao_email, obter_alteracao_email_valida,
    solicitar_alteracao_email,
)


_TOKEN_EMAIL_SESSION = "confirmacao_alteracao_email"


class EmailPrivadoMixin:
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Referrer-Policy"] = "no-referrer"
        patch_vary_headers(response, ["Cookie"])
        return response


@method_decorator(sensitive_post_parameters("senha_atual"), name="dispatch")
class AlterarEmailView(EmailPrivadoMixin, LoginRequiredMixin, FormView):
    template_name = "contas/alterar_email.html"
    form_class = AlterarEmailForm
    success_url = reverse_lazy("contas:alterar_email")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "usuario": self.request.user}

    def form_valid(self, form):
        try:
            # Falha no envio desfaz a substituição de uma solicitação anterior.
            with transaction.atomic():
                pedido, token = solicitar_alteracao_email(
                    usuario=self.request.user,
                    novo_email=form.cleaned_data["novo_email"],
                    senha_atual=form.cleaned_data["senha_atual"],
                )
                url = self.request.build_absolute_uri(reverse(
                    "contas:confirmar_email_link", kwargs={"token": token},
                ))
                enviados = send_mail(
                    "Confirme a alteração de e-mail — ShareCar",
                    render_to_string("contas/emails/alterar_email.txt", {"url": url}),
                    None, [pedido.novo_email], fail_silently=False,
                )
                if enviados != 1:
                    raise OSError("Envio de confirmação não concluído.")
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        except (OSError, SMTPException):
            form.add_error(
                None, "Não foi possível enviar a confirmação. Tente novamente mais tarde.",
            )
            return self.form_invalid(form)
        messages.success(
            self.request,
            "Confirmação enviada ao novo e-mail. Seu login atual permanece válido até confirmar.",
        )
        return super().form_valid(form)


class ConfirmarEmailLinkView(EmailPrivadoMixin, LoginRequiredMixin, View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, token):
        if obter_alteracao_email_valida(request.user, token):
            # Como na redefinição de senha do Django, retira o token da página
            # de confirmação. GET não troca o e-mail nem consome a solicitação.
            request.session[_TOKEN_EMAIL_SESSION] = token
            return redirect("contas:confirmar_email")
        request.session.pop(_TOKEN_EMAIL_SESSION, None)
        return render(
            request, "contas/confirmar_email.html", {"pedido": None}, status=400,
        )


class ConfirmarEmailView(EmailPrivadoMixin, LoginRequiredMixin, FormView):
    template_name = "contas/confirmar_email.html"
    form_class = forms.Form
    success_url = reverse_lazy("contas:perfil")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pedido"] = obter_alteracao_email_valida(
            self.request.user, self.request.session.get(_TOKEN_EMAIL_SESSION),
        )
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if not context["pedido"]:
            request.session.pop(_TOKEN_EMAIL_SESSION, None)
        return self.render_to_response(
            context, status=200 if context["pedido"] else 400,
        )

    def form_valid(self, form):
        try:
            email = confirmar_alteracao_email(
                usuario=self.request.user,
                token=self.request.session.get(_TOKEN_EMAIL_SESSION),
            )
        except ValidationError as error:
            self.request.session.pop(_TOKEN_EMAIL_SESSION, None)
            form.add_error(None, error)
            return self.render_to_response(
                self.get_context_data(form=form), status=400,
            )
        self.request.session.pop(_TOKEN_EMAIL_SESSION, None)
        self.request.session.cycle_key()
        self.request.user.email = email
        messages.success(
            self.request,
            "E-mail alterado. Use o novo endereço para entrar no site.",
        )
        return super().form_valid(form)


class LoginEmailView(LoginView):
    template_name = "core/entrar.html"
    authentication_form = LoginEmailForm


class SairView(LogoutView):
    next_page = reverse_lazy("core:entrar")

@method_decorator(never_cache, name="dispatch")
class EnviarDocumentoView(ContaPessoalMixin, LoginRequiredMixin, FormView):
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
        except OSError:
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
        response["Cross-Origin-Resource-Policy"] = "same-origin"
        response["Referrer-Policy"] = "no-referrer"
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
class PainelView(ContaPessoalMixin, LoginRequiredMixin, TemplateView):
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
