from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.contas.models import Usuario

from .forms import CadastroVeiculoForm, EdicaoVeiculoForm, FotoVeiculoForm
from .models import Veiculo


@method_decorator(never_cache, name="dispatch")
class CadastroVeiculoView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    template_name = "core/veiculo.html"
    form_class = CadastroVeiculoForm
    success_url = reverse_lazy("veiculos:meus")

    def test_func(self):
        usuario = self.request.user
        return (
            usuario.proprietario and
            usuario.aprovacao_documento == Usuario.Aprovacao.APROVADO
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(
                self.request,
                "Para anunciar, selecione o perfil de proprietário e tenha "
                "seu documento de identidade aprovado.",
            )
            return redirect("contas:perfil")
        return super().handle_no_permission()

    def form_valid(self, form):
        form.instance.proprietario = self.request.user
        form.instance.aprovacao = Veiculo.Aprovacao.PENDENTE
        form.instance.bloqueado = False
        form.instance.ativo = True
        response = super().form_valid(form)
        messages.success(
            self.request, "Veículo cadastrado e enviado para análise.",
        )
        return response


@method_decorator(never_cache, name="dispatch")
class MeusVeiculosView(LoginRequiredMixin, ListView):
    template_name = "veiculos/meus.html"
    context_object_name = "veiculos"
    paginate_by = 10

    def get_queryset(self):
        return Veiculo.objects.filter(
            proprietario=self.request.user,
        ).order_by("-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        context["pode_anunciar"] = (
            usuario.proprietario and
            usuario.aprovacao_documento == Usuario.Aprovacao.APROVADO
        )
        return context


@method_decorator(never_cache, name="dispatch")
class EditarVeiculoView(LoginRequiredMixin, UpdateView):
    template_name = "veiculos/editar.html"
    form_class = EdicaoVeiculoForm
    success_url = reverse_lazy("veiculos:meus")

    def get_queryset(self):
        return Veiculo.objects.filter(proprietario=self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Veículo atualizado com sucesso.")
        return response


@method_decorator(never_cache, name="dispatch")
class FotosVeiculoView(LoginRequiredMixin, FormView):
    template_name = "veiculos/fotos.html"
    form_class = FotoVeiculoForm

    def get_form_kwargs(self):
        self.veiculo = get_object_or_404(
            Veiculo, pk=self.kwargs["pk"], proprietario=self.request.user,
        )
        return super().get_form_kwargs()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["veiculo"] = self.veiculo
        context["fotos"] = self.veiculo.fotos.order_by("pk")
        return context

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.veiculo = self.veiculo
            form.save()
            Veiculo.objects.filter(pk=self.veiculo.pk).update(
                aprovacao=Veiculo.Aprovacao.PENDENTE,
            )
        messages.success(
            self.request, "Foto adicionada. O anúncio voltou para análise.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("veiculos:fotos", args=[self.veiculo.pk])
