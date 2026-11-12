from django.db import transaction
from django.db.models import Avg, Count, Exists, F, OuterRef

from apps.reservas.models import Reserva

from .models import Avaliacao


class AvaliacaoInvalida(Exception):
    """Indica que a avaliação não pode ser enviada no estado atual."""


def participante_da_reserva(reserva: Reserva, usuario):
    """Retorna o usuário avaliado ou None quando o autor não participa."""
    if reserva.locatario_id == reserva.veiculo.proprietario_id:
        return None
    if reserva.locatario_id == usuario.pk:
        return reserva.veiculo.proprietario
    if reserva.veiculo.proprietario_id == usuario.pk:
        return reserva.locatario
    return None


def pode_avaliar(reserva: Reserva, usuario) -> bool:
    """A avaliação é permitida uma vez por parte, após a locação concluir."""
    if reserva.status != Reserva.Status.CONCLUIDA:
        return False
    if participante_da_reserva(reserva, usuario) is None:
        return False
    return not reserva.avaliacoes.filter(autor=usuario).exists()


@transaction.atomic
def avaliar_reserva(*, reserva: Reserva, autor, nota: int) -> Avaliacao:
    """Registra a avaliação do locatário ou do proprietário."""
    if type(nota) is not int or not 1 <= nota <= 5:
        raise AvaliacaoInvalida("Informe uma nota inteira de 1 a 5.")
    atual = Reserva.objects.select_for_update().select_related(
        "veiculo",
        "veiculo__proprietario",
        "locatario",
    ).get(pk=reserva.pk)

    if atual.status != Reserva.Status.CONCLUIDA:
        raise AvaliacaoInvalida(
            "A avaliação só é liberada após a conclusão da locação."
        )

    avaliado = participante_da_reserva(atual, autor)
    if avaliado is None:
        raise AvaliacaoInvalida("Você não participa desta reserva.")
    if atual.avaliacoes.filter(autor=autor).exists():
        raise AvaliacaoInvalida("Você já avaliou esta reserva.")

    return Avaliacao.objects.create(
        reserva=atual,
        autor=autor,
        avaliado=avaliado,
        nota=nota,
    )


def avaliacoes_da_reserva(reserva: Reserva):
    """Lista as avaliações da reserva com os participantes carregados."""
    return reserva.avaliacoes.select_related("autor", "avaliado").order_by("id")


def resumo_avaliacoes_veiculo(veiculo) -> dict:
    """Agrega só notas de locatários já liberadas pela avaliação recíproca."""
    contraparte = Avaliacao.objects.filter(
        reserva_id=OuterRef("reserva_id"),
        autor_id=OuterRef("avaliado_id"),
        avaliado_id=OuterRef("autor_id"),
    )
    return Avaliacao.objects.filter(
        reserva__veiculo=veiculo,
        reserva__status=Reserva.Status.CONCLUIDA,
        autor=F("reserva__locatario"),
        avaliado=F("reserva__veiculo__proprietario"),
    ).filter(Exists(contraparte)).aggregate(media=Avg("nota"), total=Count("pk"))
