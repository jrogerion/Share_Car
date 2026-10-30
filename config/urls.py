from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/", include("apps.contas.urls")),
    path("", include("apps.core.urls")),
]
