import json
import math
from datetime import timedelta
from ipaddress import ip_address

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LimiteAcesso


# Janelas fixas: contam envios, inclusive credenciais corretas ou formulário inválido.
LIMITES = {
    "login": (20, 5, timedelta(minutes=5)),
    "recuperacao": (5, 3, timedelta(minutes=15)),
    "alteracao_email": (5, 3, timedelta(minutes=15)),
    "encerramento": (5, 3, timedelta(minutes=15)),
}


def ip_da_conexao(request):
    """Não confia em X-Forwarded-For, X-Real-IP ou outros headers do cliente."""
    try:
        return str(ip_address(request.META.get("REMOTE_ADDR", "")))
    except ValueError:
        return "desconhecido"


def _contador(acao, partes, janela):
    chave = salted_hmac(
        "contas.limites", json.dumps([acao, *partes]), algorithm="sha256",
    ).hexdigest()
    contador, _ = LimiteAcesso.objects.select_for_update().get_or_create(
        chave=chave, defaults={"expira_em": timezone.now() + janela},
    )
    return contador


def _espera(contador, agora, limite):
    if contador.expira_em <= agora:
        return 0
    if contador.tentativas >= limite:
        return max(1, math.ceil((contador.expira_em - agora).total_seconds()))
    return 0


@transaction.atomic
def consumir_tentativa(acao, ip, identificador):
    """Reserva uma tentativa atomicamente; retorna segundos de bloqueio ou zero.

    Trava sempre IP antes do par IP/identificador. Envios bloqueados não estendem
    a janela nem criam novos pares quando o limite do IP já foi alcançado.
    """
    limite_ip, limite_par, janela = LIMITES[acao]
    por_ip = _contador(acao, [ip], janela)
    espera = _espera(por_ip, timezone.now(), limite_ip)
    if espera:
        return espera
    por_par = _contador(acao, [ip, identificador.strip().lower()], janela)
    agora = timezone.now()
    espera = _espera(por_par, agora, limite_par)
    if espera:
        return espera
    for contador in (por_ip, por_par):
        if contador.expira_em <= agora:
            contador.tentativas = 0
            contador.expira_em = agora + janela
        contador.tentativas += 1
        contador.save(update_fields=["tentativas", "expira_em"])
    return 0
