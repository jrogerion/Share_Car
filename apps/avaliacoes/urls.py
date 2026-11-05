from django.urls import path

from .views import AvaliarReservaView

app_name = "avaliacoes"

urlpatterns = [
    path(
        "<int:reserva_pk>/",
        AvaliarReservaView.as_view(),
        name="avaliar",
    ),
]
