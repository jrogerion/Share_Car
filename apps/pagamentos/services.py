from django.db import transaction

from apps.reservas.models import Reserva

from .models import Pagamento


class PagamentoInvalido(Exception):
    """Indica que o pagamento não pode ser simulado no estado atual."""


@transaction.atomic
def simular_pagamento(
    *,
    reserva: Reserva,
    meio: str,
    resultado: str,
) -> Pagamento:
    """Cria ou substitui o pagamento simulado de uma reserva aceita."""
    if meio not in Pagamento.Meio.values:
        raise PagamentoInvalido("Meio de pagamento inválido.")
    if resultado not in ("aprovado", "recusado"):
        raise PagamentoInvalido("Resultado da simulação inválido.")

    # Mesmo bloqueio usado no cancelamento e no check-in: o estado e os
    # valores vêm do banco, nunca da instância ou do formulário do cliente.
    atual = Reserva.objects.select_for_update().get(pk=reserva.pk)

    if atual.status != Reserva.Status.ACEITA:
        raise PagamentoInvalido(
            "O pagamento só pode ser simulado para uma reserva aceita."
        )

    if Pagamento.objects.filter(
        reserva=atual,
        status=Pagamento.Status.APROVADO,
    ).exists():
        raise PagamentoInvalido("Esta reserva já possui pagamento aprovado.")

    status = (
        Pagamento.Status.APROVADO
        if resultado == "aprovado"
        else Pagamento.Status.RECUSADO
    )
    pagamento, _ = Pagamento.objects.update_or_create(
        reserva=atual,
        defaults={
            "meio": meio,
            "status": status,
            "valor_bruto": atual.total,
            "comissao": atual.comissao,
            "repasse_proprietario": atual.repasse_proprietario,
        },
    )
    return pagamento
