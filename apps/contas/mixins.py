from django.contrib import messages
from django.shortcuts import redirect


class ContaPessoalMixin:
    """Separa os fluxos de cliente da conta administrativa, inclusive em POST."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.conta_administrativa:
            messages.info(
                request,
                "Esta conta é exclusiva para administração. "
                "Use outra conta para alugar ou anunciar veículos.",
            )
            return redirect("administracao:painel")
        return super().dispatch(request, *args, **kwargs)
