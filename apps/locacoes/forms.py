from django import forms

from .models import RegistroLocacao
from .validacoes import QUILOMETRAGEM_MAXIMA, validar_fotos


class MultipleFileInput(forms.FileInput):
    """Input de arquivo que aceita seleção múltipla."""

    allow_multiple_selected = True


class MultipleFileField(forms.Field):
    """Campo de upload que mantém todos os arquivos selecionados."""

    widget = MultipleFileInput

    def to_python(self, data):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return list(data)
        return [data]


class RegistroLocacaoForm(forms.Form):
    """Formulário comum aos registros de check-in e check-out."""

    quilometragem = forms.IntegerField(
        label="Quilometragem",
        min_value=0,
        max_value=QUILOMETRAGEM_MAXIMA,
        widget=forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
    )
    nivel_combustivel = forms.IntegerField(
        label="Nível de combustível (%)",
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={"min": 0, "max": 100}),
    )
    fotos = MultipleFileField(
        label="Fotos do veículo",
        required=True,
        widget=MultipleFileInput(
            attrs={
                "multiple": True,
                "accept": ".jpg,.jpeg,.png",
            }
        ),
        help_text=(
            "Envie de 1 a 6 fotos em JPG ou PNG, com até 5 MB e "
            "20 megapixels cada. "
            "Registre frente, traseira, laterais, interior e painel."
        ),
    )

    def __init__(self, *args, tipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo = tipo
        if tipo == RegistroLocacao.Tipo.CHECK_OUT:
            self.fields["quilometragem"].label = "Quilometragem final"

    def clean_fotos(self):
        return validar_fotos(self.cleaned_data.get("fotos"))
