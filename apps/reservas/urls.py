from django.urls import path

from .views import (
    AceitarReservaView,
    AgendaVeiculoView,
    CancelarReservaView,
    CriarReservaView,
    DetalheReservaView,
    MinhasReservasView,
    RecusarReservaView,
    RemoverPeriodoView,
)

app_name = "reservas"

urlpatterns = [
    path("", MinhasReservasView.as_view(), name="minhas"),
    path("solicitar/<int:pk>/", CriarReservaView.as_view(), name="criar"),
    path("agenda/<int:pk>/", AgendaVeiculoView.as_view(), name="agenda"),
    path(
        "agenda/periodos/<int:pk>/remover/",
        RemoverPeriodoView.as_view(),
        name="remover_periodo",
    ),
    path("<int:pk>/", DetalheReservaView.as_view(), name="detalhe"),
    path("<int:pk>/aceitar/", AceitarReservaView.as_view(), name="aceitar"),
    path("<int:pk>/recusar/", RecusarReservaView.as_view(), name="recusar"),
    path("<int:pk>/cancelar/", CancelarReservaView.as_view(), name="cancelar"),
]
