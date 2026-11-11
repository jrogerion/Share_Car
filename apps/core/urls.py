from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

from apps.contas.forms import LoginEmailForm
from apps.veiculos.views import CadastroVeiculoView

from .pwa import manifest, offline, service_worker
from .views import DestaqueView, DetalhesVeiculoView, HomeView, ResultadosView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("destaques/<slug:slug>/", DestaqueView.as_view(), name="destaque"),
    path("manifest.webmanifest", manifest, name="manifest"),
    path("sw.js", service_worker, name="service_worker"),
    path("offline/", offline, name="offline"),
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="core/entrar.html",
            authentication_form=LoginEmailForm,
            redirect_authenticated_user=True,
        ),
        name="entrar",
    ),
    path(
        "sair/",
        auth_views.LogoutView.as_view(),
        name="sair",
    ),
    path("buscar/", ResultadosView.as_view(), name="resultados"),
    path("veiculos/<int:pk>/", DetalhesVeiculoView.as_view(), name="detalhes"),
    path("reserva/resumo/", TemplateView.as_view(template_name="core/resumo.html"), name="resumo"),
    path("reserva/pagamento/", TemplateView.as_view(template_name="core/pagamento.html"), name="pagamento"),
    path(
        "reserva/exemplos/",
        TemplateView.as_view(template_name="core/reservas.html"),
        name="reservas_exemplo",
    ),
    path("reserva/vistoria/", TemplateView.as_view(template_name="core/checkin.html"), name="checkin"),
    path("anunciar/", CadastroVeiculoView.as_view(), name="veiculo"),
    path("reserva/avaliacao/", TemplateView.as_view(template_name="core/avaliacao.html"), name="avaliacao"),
]
