from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET


@require_GET
@cache_control(public=True, max_age=3600)
def manifest(request):
    """Manifesto público, sem dados da sessão ou do usuário."""
    inicio = reverse("core:home")
    return JsonResponse({
        "id": inicio,
        "name": "ShareCar — Aluguel de carros entre pessoas",
        "short_name": "ShareCar",
        "lang": "pt-BR",
        "start_url": inicio,
        "scope": inicio,
        "display": "standalone",
        "theme_color": "#0f766e",
        "background_color": "#f7fafc",
        "icons": [{
            "src": static(f"icons/icon-{tamanho}.png"),
            "sizes": f"{tamanho}x{tamanho}",
            "type": "image/png",
            "purpose": "any",
        } for tamanho in (192, 512)],
    }, content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False})


@require_GET
def service_worker(request):
    response = render(
        request, "core/sw.js", {"offline_url": reverse("core:offline")},
        content_type="text/javascript; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = reverse("core:home")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@cache_control(public=True, max_age=3600)
def offline(request):
    # Template independente: nunca herdar o menu autenticado ou incluir CSRF.
    return render(request, "core/offline.html")
