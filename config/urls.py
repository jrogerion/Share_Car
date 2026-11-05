from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.veiculos.api_urls")),
    path("conta/", include("apps.contas.urls")),
    path("reservas/", include("apps.reservas.urls")),
    path("pagamentos/", include("apps.pagamentos.urls")),
    path("locacoes/", include("apps.locacoes.urls")),
    path("avaliacoes/", include("apps.avaliacoes.urls")),
    path("administracao/", include("apps.administracao.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
