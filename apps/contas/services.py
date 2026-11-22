import hashlib
import json
import re
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import AlteracaoEmail, Usuario
from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo


LINK_INVALIDO = (
    "Confirmação inválida ou expirada. Solicite uma nova alteração de e-mail."
)


def validar_novo_email(usuario, email):
    email = email.strip().lower()
    validate_email(email)
    if len(email) > 254:
        raise ValidationError("O e-mail deve ter no máximo 254 caracteres.")
    if email == usuario.email.strip().lower():
        raise ValidationError("Informe um e-mail diferente do atual.")
    if Usuario.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
        raise ValidationError("Não é possível usar este e-mail.")
    return email


def reservas_impedem_encerramento(usuario):
    """Inclui compromissos antigos ainda não finalizados, nos dois papéis."""
    return Reserva.objects.filter(
        Q(locatario_id=usuario.pk) | Q(veiculo__proprietario_id=usuario.pk),
        status__in=(
            Reserva.Status.SOLICITADA, Reserva.Status.ACEITA,
            Reserva.Status.EM_ANDAMENTO,
        ),
    )


class _AnunciosMudaram(Exception):
    pass


def encerrar_conta(*, usuario, senha_atual):
    """Desativa sem apagar históricos; serializa com reservas e novos anúncios."""
    for _ in range(3):
        try:
            with transaction.atomic():
                # Reservas e agenda já usam veículo antes da conta. Respeitar
                # essa ordem evita ciclos entre locatários e proprietários.
                ids = list(Veiculo.objects.select_for_update().filter(
                    proprietario_id=usuario.pk,
                ).order_by("pk").values_list("pk", flat=True))
                atual = Usuario.objects.select_for_update().get(pk=usuario.pk)
                if not atual.is_active or atual.encerrada_em is not None:
                    raise ValidationError("Esta conta não está disponível para encerramento.")
                if atual.conta_administrativa:
                    raise ValidationError("Contas administrativas não podem usar este encerramento.")
                if not check_password(senha_atual, atual.password):
                    raise ValidationError("Não foi possível confirmar sua senha atual.")
                atuais = list(Veiculo.objects.filter(
                    proprietario=atual,
                ).order_by("pk").values_list("pk", flat=True))
                if atuais != ids:
                    # Um anúncio pode ter sido criado antes do lock da conta.
                    # Recomeça em nova transação para travar o conjunto completo.
                    raise _AnunciosMudaram
                if reservas_impedem_encerramento(atual).exists():
                    raise ValidationError(
                        "Finalize, cancele ou recuse as reservas pendentes "
                        "antes de encerrar sua conta.",
                    )
                Veiculo.objects.filter(proprietario=atual).update(ativo=False)
                AlteracaoEmail.objects.filter(usuario=atual).delete()
                atual.is_active = False
                atual.encerrada_em = timezone.now()
                atual.set_unusable_password()
                atual.save(update_fields=["is_active", "encerrada_em", "password"])
                return
        except _AnunciosMudaram:
            continue
    raise ValidationError("Os anúncios mudaram durante a operação. Tente novamente.")


def _assinatura_conta(usuario):
    return salted_hmac(
        "contas.alteracao_email",
        json.dumps([usuario.pk, usuario.email, usuario.password]),
        algorithm="sha256",
    ).hexdigest()


def _hash_token(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    return hashlib.sha256(token.encode()).hexdigest()


@transaction.atomic
def solicitar_alteracao_email(*, usuario, novo_email, senha_atual):
    atual = Usuario.objects.select_for_update().get(pk=usuario.pk)
    if not atual.is_active or not check_password(senha_atual, atual.password):
        raise ValidationError("Não foi possível confirmar sua senha atual.")
    email = validar_novo_email(atual, novo_email)
    token = secrets.token_urlsafe(32)
    pedido, _ = AlteracaoEmail.objects.update_or_create(
        usuario=atual, defaults={
            "novo_email": email, "token_hash": _hash_token(token),
            "assinatura_conta": _assinatura_conta(atual),
            "expira_em": timezone.now() + timedelta(hours=1),
        },
    )
    return pedido, token


def _pedido_valido(pedido, usuario, token):
    resumo = _hash_token(token)
    return bool(
        pedido and usuario.is_active and resumo
        and pedido.expira_em > timezone.now()
        and constant_time_compare(pedido.token_hash, resumo)
        and constant_time_compare(
            pedido.assinatura_conta, _assinatura_conta(usuario),
        )
    )


def obter_alteracao_email_valida(usuario, token):
    if not _hash_token(token):
        return None
    pedido = AlteracaoEmail.objects.filter(usuario=usuario).first()
    return pedido if _pedido_valido(pedido, usuario, token) else None


def confirmar_alteracao_email(*, usuario, token):
    try:
        with transaction.atomic():
            # Mesma ordem de locks da solicitação: usuário, depois confirmação.
            atual = Usuario.objects.select_for_update().get(pk=usuario.pk)
            pedido = AlteracaoEmail.objects.select_for_update().filter(
                usuario=atual,
            ).first()
            if not _pedido_valido(pedido, atual, token):
                raise ValidationError(LINK_INVALIDO)
            atual.email = validar_novo_email(atual, pedido.novo_email)
            atual.save(update_fields=["email"])
            pedido.delete()
            return atual.email
    except IntegrityError as error:
        diag = getattr(error.__cause__, "diag", None)
        if getattr(diag, "constraint_name", None) != "contas_usuario_email_unico_ci":
            raise
        raise ValidationError(
            "Não é possível usar este e-mail. Solicite uma nova alteração.",
        ) from None
