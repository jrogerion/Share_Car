import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse

CACHE_NAME = "sharecar-v1"

ASSETS_PRECACHE = (
    "css/base.css",
    "css/home.css",
    "css/pages.css",
    "js/search-loading.js",
    "js/pwa.js",
    "images/car.svg",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "icons/maskable-512.png",
    "icons/apple-touch-icon.png",
    "icons/favicon-32.png",
)


def _urls_estaticas() -> list[str]:
    return [static(caminho) for caminho in ASSETS_PRECACHE]


def manifest(request):
    """Entrega o manifesto de instalação da PWA."""
    dados = {
        "name": "ShareCar — Aluguel de carros entre pessoas",
        "short_name": "ShareCar",
        "description": (
            "Alugue carros de pessoas da sua região com preço, "
            "disponibilidade e condições transparentes."
        ),
        "lang": "pt-BR",
        "id": reverse("core:home"),
        "start_url": reverse("core:home"),
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "portrait-primary",
        "background_color": "#f8fafc",
        "theme_color": "#0f766e",
        "categories": ["travel", "shopping"],
        "icons": [
            {
                "src": static("icons/icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("icons/icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("icons/maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "Buscar veículos",
                "short_name": "Buscar",
                "url": reverse("core:resultados"),
            },
            {
                "name": "Minhas reservas",
                "short_name": "Reservas",
                "url": reverse("reservas:minhas"),
            },
        ],
    }
    response = JsonResponse(
        dados,
        json_dumps_params={"ensure_ascii": False},
        content_type="application/manifest+json",
    )
    response["Cache-Control"] = "public, max-age=3600"
    return response


def service_worker(request):
    """Serve o service worker na raiz para que ele controle todo o site."""
    context = {
        "cache_name": CACHE_NAME,
        "offline_url": reverse("core:offline"),
        "static_url": settings.STATIC_URL,
        "assets_json": json.dumps(_urls_estaticas()),
    }
    response = render(
        request,
        "core/sw.js",
        context,
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def offline(request):
    """Exibe a tela de indisponibilidade quando não há conexão."""
    return render(request, "core/offline.html")
