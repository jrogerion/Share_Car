from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Avaliacao(models.Model):
    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, related_name="avaliacoes")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="avaliacoes_enviadas")
    avaliado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="avaliacoes_recebidas")
    # Escala não especificada: 1 a 5. Média do veículo deriva das notas dos locatários
    # aos proprietários nas reservas desse veículo; não existe avaliação extra de veículo.
    nota = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        constraints = [
            models.UniqueConstraint(fields=["reserva", "autor"], name="avaliacao_unica_por_parte"),
            models.CheckConstraint(condition=Q(nota__gte=1, nota__lte=5), name="avaliacao_nota_valida"),
            models.CheckConstraint(condition=~Q(autor=F("avaliado")), name="avaliacao_sem_autoavaliacao"),
        ]
