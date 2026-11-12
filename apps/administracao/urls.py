from django.urls import path

from .views import (
    AlternarBloqueioUsuarioView,
    AlternarBloqueioVeiculoView,
    AnaliseVeiculoView,
    ConfiguracaoComissaoView,
    DecidirCNHView,
    DecidirDocumentoView,
    DecidirVeiculoView,
    PainelAdministrativoView,
)

app_name = "administracao"

urlpatterns = [
    path("", PainelAdministrativoView.as_view(), name="painel"),
    path("comissao/", ConfiguracaoComissaoView.as_view(), name="comissao"),
    path(
        "veiculos/<int:pk>/", AnaliseVeiculoView.as_view(),
        name="analise_veiculo",
    ),
    path(
        "usuarios/<int:pk>/documento/<str:decisao>/",
        DecidirDocumentoView.as_view(),
        name="documento",
    ),
    path(
        "usuarios/<int:pk>/cnh/<str:decisao>/",
        DecidirCNHView.as_view(),
        name="cnh",
    ),
    path(
        "usuarios/<int:pk>/bloqueio/",
        AlternarBloqueioUsuarioView.as_view(),
        name="bloqueio_usuario",
    ),
    path(
        "veiculos/<int:pk>/aprovacao/<str:decisao>/",
        DecidirVeiculoView.as_view(),
        name="veiculo",
    ),
    path(
        "veiculos/<int:pk>/bloqueio/",
        AlternarBloqueioVeiculoView.as_view(),
        name="bloqueio_veiculo",
    ),
]
