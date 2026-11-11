from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.administracao.models import ConfiguracaoComissao
from apps.veiculos.disponibilidade import (
    STATUS_RESERVA_BLOQUEANTES, motivo_indisponibilidade,
)
from apps.veiculos.models import PeriodoAgenda, Veiculo

from .models import Reserva


CENTAVOS = Decimal("0.01")
COMISSAO_PADRAO = Decimal("15.00")


class ReservaInvalida(Exception):
    """Indica que a transição ou o período solicitado não é permitido."""


class AgendaInvalida(Exception):
    """Indica uma alteração de agenda incompatível com os compromissos."""


def _reservas_vigentes(veiculo):
    return Reserva.objects.filter(
        veiculo=veiculo, status__in=STATUS_RESERVA_BLOQUEANTES,
        fim__gt=timezone.localdate(),
    )


def _reservas_sem_cobertura(veiculo, disponibilidades):
    cobertura = disponibilidades.filter(
        inicio__lte=OuterRef("inicio"), fim__gte=OuterRef("fim"),
    )
    return _reservas_vigentes(veiculo).annotate(
        _coberta=Exists(cobertura),
    ).filter(_coberta=False)


@transaction.atomic
def adicionar_periodo_agenda(*, veiculo, inicio, fim, tipo):
    """Recebe datas validadas e serializa a agenda com novas reservas."""
    veiculo = Veiculo.objects.select_for_update().get(pk=veiculo.pk)
    periodos = PeriodoAgenda.objects.filter(veiculo=veiculo)
    if periodos.filter(inicio=inicio, fim=fim, tipo=tipo).exists():
        raise AgendaInvalida("Este período já está cadastrado na agenda.")
    if tipo == PeriodoAgenda.Tipo.BLOQUEADO:
        if _reservas_vigentes(veiculo).filter(
            inicio__lt=fim, fim__gt=inicio,
        ).exists():
            raise AgendaInvalida(
                "Não é possível bloquear datas de uma reserva vigente.",
            )
    else:
        disponiveis = periodos.filter(tipo=PeriodoAgenda.Tipo.DISPONIVEL)
        if _reservas_sem_cobertura(veiculo, disponiveis).exclude(
            inicio__gte=inicio, fim__lte=fim,
        ).exists():
            raise AgendaInvalida(
                "Esta disponibilidade deixaria reservas vigentes "
                "fora da agenda. "
                "Inclua um período que também cubra essas reservas.",
            )
    return PeriodoAgenda.objects.create(
        veiculo=veiculo, inicio=inicio, fim=fim, tipo=tipo,
    )


@transaction.atomic
def remover_periodo_agenda(periodo):
    veiculo = Veiculo.objects.select_for_update().get(pk=periodo.veiculo_id)
    restantes = PeriodoAgenda.objects.filter(
        veiculo=veiculo, tipo=PeriodoAgenda.Tipo.DISPONIVEL,
    ).exclude(pk=periodo.pk)
    if (
        periodo.tipo == PeriodoAgenda.Tipo.DISPONIVEL
        and restantes.exists()
        and _reservas_sem_cobertura(veiculo, restantes).exists()
    ):
        raise AgendaInvalida(
            "Este período cobre reservas vigentes. Cadastre outra "
            "disponibilidade que as cubra antes de removê-lo.",
        )
    periodo.delete()


def percentual_comissao() -> Decimal:
    """Retorna a comissão configurada, usando 15% quando não houver registro."""
    percentual = (
        ConfiguracaoComissao.objects.filter(pk=1)
        .values_list("percentual", flat=True)
        .first()
    )
    return percentual if percentual is not None else COMISSAO_PADRAO


def estimar_reserva(veiculo: Veiculo, inicio, fim) -> dict:
    """Calcula os valores previstos, sem gravar a reserva."""
    dias = (fim - inicio).days
    valor_diarias = (veiculo.preco_diaria * dias).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP,
    )
    percentual = percentual_comissao()
    comissao = (valor_diarias * percentual / 100).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP,
    )

    return {
        "dias": dias,
        "preco_diaria": veiculo.preco_diaria,
        "valor_diarias": valor_diarias,
        "percentual": percentual,
        "comissao": comissao,
        "repasse": valor_diarias - comissao,
        "total": valor_diarias,
    }


def pagamento_aprovado(reserva: Reserva) -> bool:
    """Indica se a reserva possui pagamento simulado aprovado."""
    from apps.pagamentos.models import Pagamento

    return Pagamento.objects.filter(
        reserva=reserva,
        status=Pagamento.Status.APROVADO,
    ).exists()


@transaction.atomic
def criar_reserva(
    *,
    veiculo: Veiculo,
    locatario,
    inicio,
    fim,
) -> Reserva:
    """Cria uma solicitação de reserva após validar o período e a disponibilidade."""
    if veiculo.proprietario_id == locatario.pk:
        raise ReservaInvalida("Você não pode reservar o seu próprio veículo.")

    # Serializa solicitações concorrentes para o mesmo veículo.
    veiculo = Veiculo.objects.select_for_update().get(pk=veiculo.pk)
    motivo = motivo_indisponibilidade(veiculo, inicio, fim)
    if motivo:
        raise ReservaInvalida(motivo)

    valores = estimar_reserva(veiculo, inicio, fim)
    return Reserva.objects.create(
        veiculo=veiculo,
        locatario=locatario,
        inicio=inicio,
        fim=fim,
        preco_diaria=valores["preco_diaria"],
        valor_diarias=valores["valor_diarias"],
        taxas=Decimal("0.00"),
        total=valores["total"],
        percentual_comissao=valores["percentual"],
    )


def _transicionar(reserva: Reserva, *, de: tuple[str, ...], para: str) -> Reserva:
    with transaction.atomic():
        atual = Reserva.objects.select_for_update().get(pk=reserva.pk)
        if atual.status not in de:
            raise ReservaInvalida(
                "Esta reserva não pode ser alterada no status atual."
            )
        atual.status = para
        atual.save(update_fields=["status"])
        return atual


def aceitar_reserva(reserva: Reserva) -> Reserva:
    """Aceita uma solicitação pendente."""
    return _transicionar(
        reserva,
        de=(Reserva.Status.SOLICITADA,),
        para=Reserva.Status.ACEITA,
    )


def recusar_reserva(reserva: Reserva) -> Reserva:
    """Recusa uma solicitação pendente."""
    return _transicionar(
        reserva,
        de=(Reserva.Status.SOLICITADA,),
        para=Reserva.Status.RECUSADA,
    )


@transaction.atomic
def cancelar_reserva(reserva: Reserva) -> Reserva:
    """Cancela uma solicitação/reserva e estorna o pagamento aprovado, se houver."""
    from apps.pagamentos.models import Pagamento

    atual = Reserva.objects.select_for_update().get(pk=reserva.pk)
    if atual.status not in (Reserva.Status.SOLICITADA, Reserva.Status.ACEITA):
        raise ReservaInvalida("Esta reserva não pode ser cancelada no status atual.")

    atual.status = Reserva.Status.CANCELADA
    atual.save(update_fields=["status"])
    Pagamento.objects.filter(
        reserva=atual,
        status=Pagamento.Status.APROVADO,
    ).update(status=Pagamento.Status.ESTORNADO)
    return atual
