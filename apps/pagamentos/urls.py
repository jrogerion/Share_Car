from django.urls import path

from .views import PagarReservaView

app_name = "pagamentos"

urlpatterns = [
    path("<int:reserva_pk>/", PagarReservaView.as_view(), name="pagar"),
]
