from django import forms

from .models import Pagamento


class PagamentoForm(forms.Form):
    """Formulário do pagamento simulado, sem integração financeira real."""

    meio = forms.ChoiceField(
        label="Meio de pagamento",
        choices=Pagamento.Meio.choices,
        initial=Pagamento.Meio.PIX,
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
    parcelas = forms.TypedChoiceField(
        label="Parcelamento do cartão", coerce=int, required=False,
        empty_value=1, initial=1,
        choices=[(n, f"{n}x sem juros" if n <= 6 else f"{n}x com {n}% de acréscimo único") for n in range(1, 9)],
        help_text="Pix é à vista com 5% de desconto. No cartão, 7x e 8x têm acréscimo único, não mensal.",
    )

    def clean(self):
        dados = super().clean()
        if dados.get("meio") == Pagamento.Meio.PIX and dados.get("parcelas", 1) != 1:
            self.add_error("parcelas", "O Pix deve ser pago à vista.")
        return dados
