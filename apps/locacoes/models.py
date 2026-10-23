from django.db import models
from django.db.models import Q


class RegistroLocacao(models.Model):
    class Tipo(models.TextChoices):
        CHECK_IN = "check_in", "Check-in"
        CHECK_OUT = "check_out", "Check-out"

    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, related_name="registros_locacao")
    tipo = models.CharField(max_length=9, choices=Tipo.choices)
    quilometragem = models.PositiveIntegerField()
    # Unidade não definida no enunciado: percentual inteiro de 0 a 100.
    nivel_combustivel = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "registro de locação"
        verbose_name_plural = "registros de locação"
        constraints = [
            models.UniqueConstraint(fields=["reserva", "tipo"], name="locacao_registro_unico_por_tipo"),
            models.CheckConstraint(condition=Q(nivel_combustivel__lte=100), name="locacao_combustivel_valido"),
        ]


class FotoRegistroLocacao(models.Model):
    registro = models.ForeignKey(RegistroLocacao, on_delete=models.CASCADE, related_name="fotos")
    foto = models.ImageField(upload_to="locacoes/")

    class Meta:
        verbose_name = "foto do registro de locação"
        verbose_name_plural = "fotos dos registros de locação"
