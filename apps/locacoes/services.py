from django.db import transaction

from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva

from .models import FotoRegistroLocacao, RegistroLocacao


class LocacaoInvalida(Exception):
    """Indica que o registro de locação não pode ser feito no estado atual."""


@transaction.atomic
def registrar_locacao(
    *,
    reserva: Reserva,
    tipo: str,
    quilometragem: int,
    nivel_combustivel: int,
    fotos,
) -> RegistroLocacao:
    """Registra o check-in/check-out e atualiza o status da reserva."""
    atual = Reserva.objects.select_for_update().get(pk=reserva.pk)

    if tipo == RegistroLocacao.Tipo.CHECK_IN:
        if atual.status != Reserva.Status.ACEITA:
            raise LocacaoInvalida(
                "O check-in só pode ser feito em uma reserva aceita."
            )
        if not Pagamento.objects.filter(
            reserva=atual,
            status=Pagamento.Status.APROVADO,
        ).exists():
            raise LocacaoInvalida(
                "O pagamento precisa estar aprovado para liberar o check-in."
            )
        if RegistroLocacao.objects.filter(
            reserva=atual,
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        ).exists():
            raise LocacaoInvalida("O check-in desta reserva já foi registrado.")
        novo_status = Reserva.Status.EM_ANDAMENTO
    elif tipo == RegistroLocacao.Tipo.CHECK_OUT:
        if atual.status != Reserva.Status.EM_ANDAMENTO:
            raise LocacaoInvalida(
                "O check-out só pode ser feito após o check-in."
            )
        check_in = RegistroLocacao.objects.filter(
            reserva=atual,
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        ).first()
        if check_in is None:
            raise LocacaoInvalida("Registre o check-in antes do check-out.")
        if RegistroLocacao.objects.filter(
            reserva=atual,
            tipo=RegistroLocacao.Tipo.CHECK_OUT,
        ).exists():
            raise LocacaoInvalida("O check-out desta reserva já foi registrado.")
        if quilometragem < check_in.quilometragem:
            raise LocacaoInvalida(
                "A quilometragem final não pode ser menor que a do check-in "
                f"({check_in.quilometragem} km)."
            )
        novo_status = Reserva.Status.CONCLUIDA
    else:
        raise LocacaoInvalida("Tipo de registro inválido.")

    registro = RegistroLocacao.objects.create(
        reserva=atual,
        tipo=tipo,
        quilometragem=quilometragem,
        nivel_combustivel=nivel_combustivel,
    )
    for foto in fotos:
        FotoRegistroLocacao.objects.create(registro=registro, foto=foto)

    atual.status = novo_status
    atual.save(update_fields=["status"])
    return registro


def check_in_da_reserva(reserva: Reserva) -> RegistroLocacao | None:
    """Retorna o check-in registrado, se existir."""
    return (
        RegistroLocacao.objects.filter(
            reserva=reserva,
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        )
        .prefetch_related("fotos")
        .first()
    )


def check_out_da_reserva(reserva: Reserva) -> RegistroLocacao | None:
    """Retorna o check-out registrado, se existir."""
    return (
        RegistroLocacao.objects.filter(
            reserva=reserva,
            tipo=RegistroLocacao.Tipo.CHECK_OUT,
        )
        .prefetch_related("fotos")
        .first()
    )
