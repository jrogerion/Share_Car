from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import F, Q


class Reserva(models.Model):
    class Status(models.TextChoices):
        SOLICITADA = "solicitada", "Solicitada"
        ACEITA = "aceita", "Aceita"
        RECUSADA = "recusada", "Recusada"
        CANCELADA = "cancelada", "Cancelada"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        CONCLUIDA = "concluida", "Concluída"

    veiculo = models.ForeignKey("veiculos.Veiculo", on_delete=models.PROTECT, related_name="reservas")
    locatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservas")
    inicio = models.DateField()
    fim = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SOLICITADA)
    # Valores contratados são snapshots; não acompanham alterações futuras da diária/comissão.
    preco_diaria = models.DecimalField(max_digits=10, decimal_places=2)
    valor_diarias = models.DecimalField(max_digits=12, decimal_places=2)
    taxas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    percentual_comissao = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        constraints = [
            models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="reserva_periodo_valido"),
            models.CheckConstraint(condition=Q(preco_diaria__gt=0, valor_diarias__gt=0, taxas__gte=0), name="reserva_valores_validos"),
            models.CheckConstraint(condition=Q(total=F("valor_diarias") + F("taxas")), name="reserva_total_consistente"),
            models.CheckConstraint(condition=Q(percentual_comissao__gte=0, percentual_comissao__lte=100), name="reserva_comissao_valida"),
            # Solicitada já ocupa a agenda: duas solicitações concorrentes não podem vencer.
            # Concluídas preservam a exclusividade do histórico. Recusas/cancelamentos liberam.
            ExclusionConstraint(
                name="reserva_sem_sobreposicao",
                expressions=[
                    ("veiculo", RangeOperators.EQUAL),
                    (models.Func("inicio", "fim", models.Value("[)"), function="DATERANGE", output_field=DateRangeField()), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=["solicitada", "aceita", "em_andamento", "concluida"]),
            ),
        ]
