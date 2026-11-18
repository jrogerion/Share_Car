import warnings
from io import BytesIO
from uuid import uuid4

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def preparar_imagem_privada(arquivo):
    """Recria JPEG/PNG sem metadados ou bytes extras e com nome não pessoal."""
    if arquivo.size > 5 * 1024 * 1024:
        raise forms.ValidationError("A imagem deve ter no máximo 5 MB.")
    buffer = BytesIO()
    try:
        arquivo.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(arquivo) as original:
                formato = original.format
                if formato not in ("JPEG", "PNG"):
                    raise forms.ValidationError("Envie uma imagem JPEG ou PNG válida.")
                if original.width * original.height > 20_000_000:
                    raise forms.ValidationError("A imagem deve ter até 20 megapixels.")
                imagem = ImageOps.exif_transpose(original)
                imagem = imagem.convert("RGB" if formato == "JPEG" else "RGBA")
                imagem.info.clear()
                imagem.save(buffer, format=formato)
    except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise forms.ValidationError("Não foi possível processar a imagem.") from exc
    if buffer.tell() > 5 * 1024 * 1024:
        raise forms.ValidationError("Reduza a imagem para até 5 MB.")
    extensao = "jpg" if formato == "JPEG" else "png"
    return ContentFile(buffer.getvalue(), name=f"{uuid4().hex}.{extensao}")
