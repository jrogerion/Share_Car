from django import forms

from .models import ConfiguracaoComissao


class PeriodoDashboardForm(forms.Form):
    inicio = forms.DateField(
        label="Retirada a partir de", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    fim = forms.DateField(
        label="Retirada até", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            self.add_error("fim", "A data final deve ser igual ou posterior à inicial.")
        return dados


class ConfiguracaoComissaoForm(forms.ModelForm):
    """Atualiza a comissão global aplicada às novas reservas."""

    class Meta:
        model = ConfiguracaoComissao
        fields = ("percentual",)
        labels = {"percentual": "Percentual da comissão (%)"}
        widgets = {
            "percentual": forms.NumberInput(
                attrs={"min": "0", "max": "100", "step": "0.01"}
            ),
        }

    def clean_percentual(self):
        percentual = self.cleaned_data["percentual"]
        if percentual < 0 or percentual > 100:
            raise forms.ValidationError(
                "O percentual deve estar entre 0 e 100."
            )
        return percentual
