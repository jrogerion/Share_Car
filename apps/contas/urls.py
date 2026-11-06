from django.urls import path

from .views import (
    CadastroConcluidoView, CadastroUsuarioView, DocumentoIdentidadeView,
    EnviarDocumentoView, PerfilUsuarioView, SairView,
)

app_name = "contas"

urlpatterns = [
    path("perfil/", PerfilUsuarioView.as_view(), name="perfil"),
    path(
        "documento/enviar/", EnviarDocumentoView.as_view(),
        name="enviar_documento",
    ),
    path(
        "usuarios/<int:pk>/documento/", DocumentoIdentidadeView.as_view(),
        name="documento_identidade",
    ),
    path("sair/", SairView.as_view(), name="sair"),
    path("cadastro/", CadastroUsuarioView.as_view(), name="cadastro"),
    path(
        "cadastro/concluido/", CadastroConcluidoView.as_view(),
        name="cadastro_concluido",
    ),
]
