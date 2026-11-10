from django.urls import path

from .views import EditarVeiculoView, FotosVeiculoView, MeusVeiculosView

app_name = "veiculos"

urlpatterns = [
    path("meus/", MeusVeiculosView.as_view(), name="meus"),
    path("<int:pk>/editar/", EditarVeiculoView.as_view(), name="editar"),
    path("<int:pk>/fotos/", FotosVeiculoView.as_view(), name="fotos"),
]
