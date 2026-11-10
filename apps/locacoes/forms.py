from django import forms
from django.core.validators import FileExtensionValidator

from .models import RegistroLocacao

TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024
MAXIMO_FOTOS = 6
EXTENSOES_FOTO = ["jpg", "jpeg", "png"]
TIPOS_FOTO = {"image/jpeg", "image/png"}


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
            "Envie de 1 a 6 fotos em JPG ou PNG, com até 5 MB cada. "
            "Registre frente, traseira, laterais, interior e painel."
        ),
    )

    def __init__(self, *args, tipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo = tipo
        if tipo == RegistroLocacao.Tipo.CHECK_OUT:
            self.fields["quilometragem"].label = "Quilometragem final"

    def clean_fotos(self):
        arquivos = self.cleaned_data.get("fotos") or []
        if not isinstance(arquivos, (list, tuple)):
            arquivos = [arquivos]
        arquivos = list(arquivos)

        if not arquivos:
            raise forms.ValidationError("Envie ao menos uma foto do veículo.")
        if len(arquivos) > MAXIMO_FOTOS:
            raise forms.ValidationError(
                f"Envie no máximo {MAXIMO_FOTOS} fotos por registro."
            )

        validador_extensao = FileExtensionValidator(EXTENSOES_FOTO)
        for arquivo in arquivos:
            if arquivo.size > TAMANHO_MAXIMO_FOTO:
                raise forms.ValidationError(
                    "Cada foto deve ter no máximo 5 MB."
                )

            tipo = getattr(arquivo, "content_type", None)
            if tipo and tipo not in TIPOS_FOTO:
                raise forms.ValidationError(
                    "Envie as fotos em JPG ou PNG."
                )

            try:
                validador_extensao(arquivo)
            except forms.ValidationError as exc:
                raise forms.ValidationError(
                    "Envie as fotos em JPG ou PNG."
                ) from exc

        return arquivos
