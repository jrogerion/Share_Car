from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import CadastroView, PainelView, PerfilView

app_name = "contas"

urlpatterns = [
    path("cadastro/", CadastroView.as_view(), name="cadastro"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("painel/", PainelView.as_view(), name="painel"),
    path(
        "senha/recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="contas/recuperar_senha.html",
            email_template_name="contas/emails/recuperar_senha.txt",
            subject_template_name="contas/emails/recuperar_senha_assunto.txt",
            success_url=reverse_lazy("contas:recuperar_senha_enviado"),
        ),
        name="recuperar_senha",
    ),
    path(
        "senha/recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="contas/recuperar_senha_enviado.html",
        ),
        name="recuperar_senha_enviado",
    ),
    path(
        "senha/redefinir/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="contas/redefinir_senha.html",
            success_url=reverse_lazy("contas:redefinir_senha_concluido"),
        ),
        name="redefinir_senha",
    ),
    path(
        "senha/redefinir/concluido/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="contas/redefinir_senha_concluido.html",
        ),
        name="redefinir_senha_concluido",
    ),
    path(
        "senha/alterar/",
        auth_views.PasswordChangeView.as_view(
            template_name="contas/alterar_senha.html",
            success_url=reverse_lazy("contas:alterar_senha_concluido"),
        ),
        name="alterar_senha",
    ),
    path(
        "senha/alterar/concluido/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="contas/alterar_senha_concluido.html",
        ),
        name="alterar_senha_concluido",
    ),
]
