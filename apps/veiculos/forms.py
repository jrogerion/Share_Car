from decimal import Decimal

from django import forms
from django.utils import timezone

from .consultas import veiculos_publicos


class PeriodoReservaMixin:
    """Valida o período [retirada, devolução) usado na busca e na reserva."""

    def clean_periodo(self):
        if self.errors.get("retirada") or self.errors.get("devolucao"):
            return None, None

        retirada = self.cleaned_data.get("retirada")
        devolucao = self.cleaned_data.get("devolucao")

        if not retirada and not devolucao:
            return retirada, devolucao

        if not retirada or not devolucao:
            campo = "devolucao" if retirada else "retirada"
            self.add_error(campo, "Informe a retirada e a devolução juntas.")
            return retirada, devolucao

        if retirada < timezone.localdate():
            self.add_error("retirada", "A retirada não pode estar no passado.")

        if devolucao <= retirada:
            self.add_error(
                "devolucao",
                "A devolução deve ser posterior à retirada.",
            )

        return retirada, devolucao


class BuscaVeiculoForm(PeriodoReservaMixin, forms.Form):
    """Filtros públicos da busca de veículos."""

    retirada = forms.DateField(
        label="Retirada",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    devolucao = forms.DateField(
        label="Devolução",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
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
        hoje = timezone.localdate().isoformat()
        for campo in ("retirada", "devolucao"):
            self.fields[campo].widget.attrs["min"] = hoje
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
        self.clean_periodo()
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
