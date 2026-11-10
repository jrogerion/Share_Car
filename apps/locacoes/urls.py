from django.urls import path

from .views import RegistrarLocacaoView

app_name = "locacoes"

urlpatterns = [
    path(
        "<int:reserva_pk>/check-in/",
        RegistrarLocacaoView.as_view(),
        {"tipo": "check_in"},
        name="check_in",
    ),
    path(
        "<int:reserva_pk>/check-out/",
        RegistrarLocacaoView.as_view(),
        {"tipo": "check_out"},
        name="check_out",
    ),
]
