from django import forms

from .models import ConfiguracaoComissao


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
