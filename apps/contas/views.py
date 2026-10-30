from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from .forms import CadastroUsuarioForm
from .models import Usuario


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
