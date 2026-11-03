from decimal import Decimal

from django import forms

from .consultas import veiculos_publicos


class BuscaVeiculoForm(forms.Form):
    """Filtros públicos da busca de veículos."""

    cidade = forms.CharField(
        label="Cidade",
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ex.: São Paulo",
                "autocomplete": "address-level2",
            }
        ),
    )
    categoria = forms.ChoiceField(label="Categoria", required=False)
    cambio = forms.ChoiceField(label="Câmbio", required=False)
    combustivel = forms.ChoiceField(label="Combustível", required=False)
    passageiros = forms.IntegerField(
        label="Capacidade mínima (passageiros)",
        required=False,
        min_value=1,
        max_value=99,
        widget=forms.NumberInput(attrs={"min": 1, "max": 99, "placeholder": "Ex.: 5"}),
    )
    diaria_min = forms.DecimalField(
        label="Diária mínima (R$)",
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={"min": "0.01", "step": "0.01", "placeholder": "Ex.: 100"}
        ),
    )
    diaria_max = forms.DecimalField(
        label="Diária máxima (R$)",
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={"min": "0.01", "step": "0.01", "placeholder": "Ex.: 300"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        publicos = veiculos_publicos()
        self.fields["categoria"].choices = [("", "Todas")] + self._opcoes(
            publicos, "categoria"
        )
        self.fields["cambio"].choices = [("", "Todos")] + self._opcoes(
            publicos, "cambio"
        )
        self.fields["combustivel"].choices = [("", "Todos")] + self._opcoes(
            publicos, "combustivel"
        )

    def clean(self):
        dados = super().clean()
        minimo = dados.get("diaria_min")
        maximo = dados.get("diaria_max")

        if minimo is not None and maximo is not None and minimo > maximo:
            self.add_error(
                "diaria_max",
                "A diária máxima deve ser maior ou igual à mínima.",
            )

        return dados

    @staticmethod
    def _opcoes(veiculos, campo: str) -> list[tuple[str, str]]:
        valores = (
            veiculos.exclude(**{campo: ""})
            .values_list(campo, flat=True)
            .distinct()
            .order_by(campo)
        )
        return [(valor, valor) for valor in valores]
