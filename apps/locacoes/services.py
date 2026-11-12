from django.core.exceptions import ValidationError
from django.db import transaction

from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva

from .models import FotoRegistroLocacao, RegistroLocacao
from .validacoes import QUILOMETRAGEM_MAXIMA, validar_fotos


class LocacaoInvalida(Exception):
    """Indica que o registro de locação não pode ser feito no estado atual."""


def motivo_impedimento_registro(reserva, tipo):
    """Orienta a interface; o serviço repete a checagem sob bloqueio."""
    if tipo == RegistroLocacao.Tipo.CHECK_IN:
        if reserva.status != Reserva.Status.ACEITA:
            return "O check-in só pode ser feito em uma reserva aceita."
        if not Pagamento.objects.filter(
            reserva=reserva, status=Pagamento.Status.APROVADO,
        ).exists():
            return "O pagamento precisa estar aprovado para liberar o check-in."
    elif tipo == RegistroLocacao.Tipo.CHECK_OUT:
        if reserva.status != Reserva.Status.EM_ANDAMENTO:
            return "O check-out só pode ser feito após o check-in."
        if not RegistroLocacao.objects.filter(
            reserva=reserva, tipo=RegistroLocacao.Tipo.CHECK_IN,
        ).exists():
            return "Registre o check-in antes do check-out."
    else:
        return "Tipo de registro inválido."
    if RegistroLocacao.objects.filter(reserva=reserva, tipo=tipo).exists():
        return "Este registro de locação já foi realizado."
    return ""


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
    if (
        type(quilometragem) is not int
        or not 0 <= quilometragem <= QUILOMETRAGEM_MAXIMA
    ):
        raise LocacaoInvalida("Informe uma quilometragem válida.")
    if type(nivel_combustivel) is not int or not 0 <= nivel_combustivel <= 100:
        raise LocacaoInvalida("Informe o combustível de 0 a 100%.")
    try:
        fotos = validar_fotos(fotos)
    except ValidationError as exc:
        raise LocacaoInvalida(" ".join(exc.messages)) from exc

    atual = Reserva.objects.select_for_update().get(pk=reserva.pk)
    impedimento = motivo_impedimento_registro(atual, tipo)
    if impedimento:
        raise LocacaoInvalida(impedimento)

    if tipo == RegistroLocacao.Tipo.CHECK_IN:
        novo_status = Reserva.Status.EM_ANDAMENTO
    else:
        check_in = RegistroLocacao.objects.filter(
            reserva=atual,
            tipo=RegistroLocacao.Tipo.CHECK_IN,
        ).first()
        if quilometragem < check_in.quilometragem:
            raise LocacaoInvalida(
                "A quilometragem final não pode ser menor que a do check-in "
                f"({check_in.quilometragem} km)."
            )
        novo_status = Reserva.Status.CONCLUIDA

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
