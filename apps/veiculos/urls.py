from django.urls import path

from .views import MeusVeiculosView

app_name = "veiculos"

urlpatterns = [
    path("meus/", MeusVeiculosView.as_view(), name="meus"),
]
