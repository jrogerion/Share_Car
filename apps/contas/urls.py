from django.urls import path

from .views import CadastroConcluidoView, CadastroUsuarioView

app_name = "contas"

urlpatterns = [
    path("cadastro/", CadastroUsuarioView.as_view(), name="cadastro"),
    path(
        "cadastro/concluido/", CadastroConcluidoView.as_view(),
        name="cadastro_concluido",
    ),
]
