from django.urls import path
from django.views.generic import TemplateView

from .views import HomeView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("entrar/", TemplateView.as_view(template_name="core/entrar.html"), name="entrar"),
    path("buscar/", TemplateView.as_view(template_name="core/resultados.html"), name="resultados"),
    path("veiculo/", TemplateView.as_view(template_name="core/detalhes.html"), name="detalhes"),
    path("reserva/resumo/", TemplateView.as_view(template_name="core/resumo.html"), name="resumo"),
    path("reserva/pagamento/", TemplateView.as_view(template_name="core/pagamento.html"), name="pagamento"),
    path("reservas/", TemplateView.as_view(template_name="core/reservas.html"), name="reservas"),
    path("reserva/vistoria/", TemplateView.as_view(template_name="core/checkin.html"), name="checkin"),
    path("anunciar/", TemplateView.as_view(template_name="core/veiculo.html"), name="veiculo"),
    path("reserva/avaliacao/", TemplateView.as_view(template_name="core/avaliacao.html"), name="avaliacao"),
]
