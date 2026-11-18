import posixpath
from pathlib import Path

from django.http import Http404
from django.views.static import serve


def servir_media_publica(request, path, document_root=None):
    """Em desenvolvimento, publica apenas fotos de anúncios, nunca vistorias."""
    normalizado = posixpath.normpath(path).lstrip("/")
    if not normalizado.startswith("veiculos/"):
        raise Http404("Arquivo não encontrado.")
    raiz = Path(document_root).resolve()
    pasta = raiz / "veiculos"
    destino = (raiz / normalizado).resolve()
    if not destino.is_relative_to(pasta):
        raise Http404("Arquivo não encontrado.")
    return serve(request, normalizado, document_root=document_root)
