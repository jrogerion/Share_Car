from django.urls import path

from .api import VeiculoDetailAPIView, VeiculoListAPIView

app_name = "veiculos_api"

urlpatterns = [
    path("veiculos/", VeiculoListAPIView.as_view(), name="lista"),
    path(
        "veiculos/<int:pk>/",
        VeiculoDetailAPIView.as_view(),
        name="detalhe",
    ),
]
