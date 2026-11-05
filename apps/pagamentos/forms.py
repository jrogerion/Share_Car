from django import forms

from .models import Pagamento


class PagamentoForm(forms.Form):
    """Formulário do pagamento simulado, sem integração financeira real."""

    meio = forms.ChoiceField(
        label="Meio de pagamento",
        choices=Pagamento.Meio.choices,
        widget=forms.RadioSelect,
    )
    resultado = forms.ChoiceField(
        label="Resultado da simulação",
        choices=(
            ("aprovado", "Aprovar o pagamento"),
            ("recusado", "Simular recusa"),
        ),
        initial="aprovado",
        widget=forms.RadioSelect,
    )
