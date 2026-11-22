from django.shortcuts import render
from django.utils.cache import add_never_cache_headers
from django.utils.deprecation import MiddlewareMixin

from .limites import consumir_tentativa, ip_da_conexao


class LimiteAutenticacaoMiddleware(MiddlewareMixin):
    """Limita entradas reais por nome de rota, incluindo aliases e Django Admin."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != "POST":
            return None
        rota = request.resolver_match.view_name
        if rota in ("core:entrar", "admin:login"):
            acao, campo = "login", "username"
        elif rota in (
            "contas:recuperar_senha", "contas_legacy:recuperar_senha",
        ):
            acao, campo = "recuperacao", "email"
        elif rota in (
            "contas:alterar_email", "contas_legacy:alterar_email",
        ):
            if not request.user.is_authenticated:
                return None
            acao, campo = "alteracao_email", None
        elif rota in (
            "contas:encerrar", "contas_legacy:encerrar",
        ):
            if not request.user.is_authenticated:
                return None
            acao, campo = "encerramento", None
        else:
            return None
        identificador = (
            str(request.user.pk) if campo is None else request.POST.get(campo, "")
        )
        espera = consumir_tentativa(
            acao, ip_da_conexao(request), identificador,
        )
        if not espera:
            return None
        response = render(request, "contas/limite_acesso.html", {
            "espera": espera,
        }, status=429)
        response["Retry-After"] = str(espera)
        add_never_cache_headers(response)
        return response
