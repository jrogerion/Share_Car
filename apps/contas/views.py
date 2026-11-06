from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponseRedirect
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
    template_name = "contas/perfil.html"
    form_class = PerfilUsuarioForm
    success_url = reverse_lazy("contas:perfil")

    def get_object(self, queryset=None):
        # A identidade vem da sessão, nunca de um ID enviado pelo cliente.
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

    def form_valid(self, form):
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            # Duas requisições podem validar o mesmo e-mail simultaneamente.
            if not Usuario.objects.filter(
                email__iexact=form.cleaned_data["email"],
            ).exists():
                raise
            form.add_error("email", "Não é possível cadastrar este e-mail.")
            return self.form_invalid(form)
        return HttpResponseRedirect(self.get_success_url())


class CadastroConcluidoView(TemplateView):
    template_name = "contas/cadastro_concluido.html"
