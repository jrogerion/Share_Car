from django.urls import path

from .views import (
    CadastroConcluidoView, CadastroUsuarioView, PerfilUsuarioView, SairView,
)

app_name = "contas"

urlpatterns = [
    path("perfil/", PerfilUsuarioView.as_view(), name="perfil"),
    path("sair/", SairView.as_view(), name="sair"),
    path("cadastro/", CadastroUsuarioView.as_view(), name="cadastro"),
    path(
        "cadastro/concluido/", CadastroConcluidoView.as_view(),
        name="cadastro_concluido",
    ),
]
