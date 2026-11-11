from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
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


def motivo_impedimento_locatario(usuario, fim=None):
    """Explica a elegibilidade sem expor número ou imagem da CNH."""
    if not usuario.is_active:
        return "A conta do locatário precisa estar ativa."
    if not usuario.locatario:
        return "Selecione o perfil de locatário em Minha conta para reservar."
    if not usuario.cnh_numero.strip() or not usuario.cnh_validade:
        return "Informe número e validade da CNH em Minha conta."
    if usuario.aprovacao_cnh != usuario.Aprovacao.APROVADO:
        return "A CNH do locatário precisa estar aprovada pela administração."
    if usuario.cnh_validade < timezone.localdate():
        return "A CNH do locatário está vencida."
    if fim and usuario.cnh_validade < fim:
        return "A CNH deve estar válida até a data de devolução."
    return ""


def motivo_impedimento_aceite(reserva):
    if reserva.veiculo.proprietario_id == reserva.locatario_id:
        return "Você não pode reservar o seu próprio veículo."
    if reserva.inicio < timezone.localdate():
        return "Não é possível aceitar uma solicitação com início no passado."
    if reserva.veiculo.motivos_nao_publicacao:
        return "O veículo precisa estar publicado para aceitar a solicitação."
    return motivo_impedimento_locatario(reserva.locatario, reserva.fim) or (
        motivo_indisponibilidade(
            reserva.veiculo, reserva.inicio, reserva.fim,
            reserva_ignorada=reserva.pk,
        )
    )


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
    if dias <= 0:
        raise ReservaInvalida("A devolução deve ser posterior à retirada.")
    valor_diarias = (veiculo.preco_diaria * dias).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP,
    )
    if valor_diarias > Decimal("9999999999.99"):
        raise ReservaInvalida(
            "O total excede o limite permitido. Reduza o período.",
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
    # O anúncio e a conta podem ter sido alterados desde a abertura da página.
    veiculo = Veiculo.objects.select_for_update().get(pk=veiculo.pk)
    if veiculo.proprietario_id == locatario.pk:
        raise ReservaInvalida("Você não pode reservar o seu próprio veículo.")
    if veiculo.motivos_nao_publicacao:
        raise ReservaInvalida(
            "O veículo não está disponível para novas reservas.",
        )
    locatario = get_user_model().objects.select_for_update().get(
        pk=locatario.pk,
    )
    impedimento = motivo_impedimento_locatario(locatario, fim)
    if impedimento:
        raise ReservaInvalida(impedimento)
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


@transaction.atomic
def aceitar_reserva(reserva: Reserva) -> Reserva:
    """Aceita uma solicitação pendente."""
    # Usa a mesma ordem de bloqueios da solicitação e da agenda.
    veiculo = Veiculo.objects.select_for_update().get(pk=reserva.veiculo_id)
    atual = Reserva.objects.select_for_update().get(pk=reserva.pk)
    if atual.status != Reserva.Status.SOLICITADA:
        raise ReservaInvalida(
            "Esta reserva não pode ser alterada no status atual.",
        )
    atual.veiculo = veiculo
    atual.locatario = get_user_model().objects.select_for_update().get(
        pk=atual.locatario_id,
    )
    motivo = motivo_impedimento_aceite(atual)
    if motivo:
        raise ReservaInvalida(motivo)
    atual.status = Reserva.Status.ACEITA
    atual.save(update_fields=["status"])
    return atual


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
