import warnings

from django import forms
from django.core.validators import FileExtensionValidator
from PIL import Image


TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024
MAXIMO_FOTOS = 6
MAXIMO_PIXELS = 20_000_000
QUILOMETRAGEM_MAXIMA = 2_147_483_647


def validar_fotos(arquivos):
    """Verifica todas as imagens antes de persistir uma vistoria."""
    arquivos = list(arquivos or [])
    if not arquivos:
        raise forms.ValidationError("Envie ao menos uma foto do veículo.")
    if len(arquivos) > MAXIMO_FOTOS:
        raise forms.ValidationError(
            f"Envie no máximo {MAXIMO_FOTOS} fotos por registro.",
        )

    campo = forms.ImageField(validators=[
        FileExtensionValidator(["jpg", "jpeg", "png"]),
    ])
    for arquivo in arquivos:
        if arquivo.size > TAMANHO_MAXIMO_FOTO:
            raise forms.ValidationError("Cada foto deve ter no máximo 5 MB.")
        tipo = getattr(arquivo, "content_type", None)
        if tipo and tipo not in {"image/jpeg", "image/png"}:
            raise forms.ValidationError("Envie as fotos em JPG ou PNG.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                campo.clean(arquivo)
                if arquivo.image.format not in {"JPEG", "PNG"}:
                    raise forms.ValidationError("Envie as fotos em JPG ou PNG.")
                if arquivo.image.width * arquivo.image.height > MAXIMO_PIXELS:
                    raise forms.ValidationError(
                        "Cada foto deve ter até 20 megapixels.",
                    )
                arquivo.seek(0)
                with Image.open(arquivo) as imagem:
                    imagem.load()
        except (OSError, ValueError, Image.DecompressionBombWarning) as exc:
            raise forms.ValidationError(
                "Envie uma imagem JPG ou PNG válida.",
            ) from exc
        finally:
            arquivo.seek(0)
    return arquivos
