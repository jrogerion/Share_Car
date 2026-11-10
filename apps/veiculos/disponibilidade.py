from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from apps.reservas.models import Reserva

from .models import PeriodoAgenda, Veiculo


STATUS_RESERVA_BLOQUEANTES = (
    Reserva.Status.SOLICITADA,
    Reserva.Status.ACEITA,
    Reserva.Status.EM_ANDAMENTO,
    Reserva.Status.CONCLUIDA,
)


def filtrar_por_disponibilidade(
    veiculos: QuerySet[Veiculo],
    inicio,
    fim,
) -> QuerySet[Veiculo]:
    """
    Restringe o conjunto aos veículos livres no intervalo [inicio, fim).

    Um veículo é considerado indisponível quando:
    - possui período de agenda do tipo bloqueado com sobreposição;
    - possui reserva ativa com sobreposição;
    - possui períodos de disponibilidade cadastrados e o intervalo solicitado
      não está contido em um deles.
    """
    bloqueio = PeriodoAgenda.objects.filter(
        veiculo=OuterRef("pk"),
        tipo=PeriodoAgenda.Tipo.BLOQUEADO,
        inicio__lt=fim,
        fim__gt=inicio,
    )
    disponibilidade = PeriodoAgenda.objects.filter(
        veiculo=OuterRef("pk"),
        tipo=PeriodoAgenda.Tipo.DISPONIVEL,
    )
    dentro_disponibilidade = PeriodoAgenda.objects.filter(
        veiculo=OuterRef("pk"),
        tipo=PeriodoAgenda.Tipo.DISPONIVEL,
        inicio__lte=inicio,
        fim__gte=fim,
    )
    reserva = Reserva.objects.filter(
        veiculo=OuterRef("pk"),
        status__in=STATUS_RESERVA_BLOQUEANTES,
        inicio__lt=fim,
        fim__gt=inicio,
    )

    return (
        veiculos.annotate(
            _tem_bloqueio=Exists(bloqueio),
            _tem_disponibilidade=Exists(disponibilidade),
            _dentro_disponibilidade=Exists(dentro_disponibilidade),
            _tem_reserva=Exists(reserva),
        )
        .filter(_tem_bloqueio=False, _tem_reserva=False)
        .filter(
            Q(_tem_disponibilidade=False)
            | Q(_dentro_disponibilidade=True)
        )
    )


def motivo_indisponibilidade(veiculo: Veiculo, inicio, fim) -> str:
    """Retorna a razão da indisponibilidade ou string vazia se estiver livre."""
    if fim <= inicio:
        return "A devolução deve ser posterior à retirada."

    if inicio < timezone.localdate():
        return "A retirada não pode estar no passado."

    if PeriodoAgenda.objects.filter(
        veiculo=veiculo,
        tipo=PeriodoAgenda.Tipo.BLOQUEADO,
        inicio__lt=fim,
        fim__gt=inicio,
    ).exists():
        return "O veículo está bloqueado no período informado."

    if Reserva.objects.filter(
        veiculo=veiculo,
        status__in=STATUS_RESERVA_BLOQUEANTES,
        inicio__lt=fim,
        fim__gt=inicio,
    ).exists():
        return "O veículo já possui uma reserva no período informado."

    if PeriodoAgenda.objects.filter(
        veiculo=veiculo,
        tipo=PeriodoAgenda.Tipo.DISPONIVEL,
    ).exists() and not PeriodoAgenda.objects.filter(
        veiculo=veiculo,
        tipo=PeriodoAgenda.Tipo.DISPONIVEL,
        inicio__lte=inicio,
        fim__gte=fim,
    ).exists():
        return "O período informado está fora da disponibilidade do veículo."

    return ""
