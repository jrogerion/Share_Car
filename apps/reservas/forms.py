from django import forms
from django.utils import timezone

from apps.veiculos.forms import PeriodoReservaMixin
from apps.veiculos.models import PeriodoAgenda


class ReservaForm(PeriodoReservaMixin, forms.Form):
    """Solicita um período de reserva para um veículo público."""

    retirada = forms.DateField(
        label="Retirada",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    devolucao = forms.DateField(
        label="Devolução",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate().isoformat()
        for campo in ("retirada", "devolucao"):
            self.fields[campo].widget.attrs["min"] = hoje

    def clean(self):
        dados = super().clean()
        self.clean_periodo()
        return dados


class PeriodoAgendaForm(forms.ModelForm):
    """Cadastra um período de disponibilidade ou bloqueio do veículo."""

    class Meta:
        model = PeriodoAgenda
        fields = ("inicio", "fim", "tipo")
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate().isoformat()
        for campo in ("inicio", "fim"):
            self.fields[campo].widget.attrs["min"] = hoje

    def clean(self):
        dados = super().clean()
        inicio = dados.get("inicio")
        fim = dados.get("fim")

        if inicio and fim and fim <= inicio:
            self.add_error(
                "fim",
                "O fim deve ser posterior ao início do período.",
            )

        if fim and fim < timezone.localdate():
            self.add_error("fim", "O período não pode terminar no passado.")

        return dados

