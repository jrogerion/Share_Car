from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Veiculo(models.Model):
    class Aprovacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        REJEITADO = "rejeitado", "Rejeitado"

    proprietario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="veiculos")
    # Características não enumeradas no RF06: descrição livre e filtros explícitos do RF10.
    caracteristicas = models.TextField()
    cidade = models.CharField(max_length=150, db_index=True)
    categoria = models.CharField(max_length=50)
    cambio = models.CharField(max_length=50)
    combustivel = models.CharField(max_length=50)
    passageiros = models.PositiveSmallIntegerField()
    preco_diaria = models.DecimalField(max_digits=10, decimal_places=2)
    ativo = models.BooleanField(default=True)
    bloqueado = models.BooleanField(default=False)
    aprovacao = models.CharField(max_length=10, choices=Aprovacao.choices, default=Aprovacao.PENDENTE)

    class Meta:
        verbose_name = "veículo"
        verbose_name_plural = "veículos"
        constraints = [
            models.CheckConstraint(condition=Q(preco_diaria__gt=0), name="veiculo_diaria_positiva"),
            models.CheckConstraint(condition=Q(passageiros__gt=0), name="veiculo_passageiros_positivos"),
        ]


class FotoVeiculo(models.Model):
    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name="fotos")
    foto = models.ImageField(upload_to="veiculos/")

    class Meta:
        verbose_name = "foto do veículo"
        verbose_name_plural = "fotos dos veículos"


class PeriodoAgenda(models.Model):
    class Tipo(models.TextChoices):
        DISPONIVEL = "disponivel", "Disponível"
        BLOQUEADO = "bloqueado", "Bloqueado"

    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name="periodos_agenda")
    inicio = models.DateField()
    fim = models.DateField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    # Diárias usam [início, fim); bloqueios prevalecem sobre disponibilidade na futura busca.

    class Meta:
        verbose_name = "período da agenda"
        verbose_name_plural = "períodos da agenda"
        constraints = [models.CheckConstraint(condition=Q(fim__gt=F("inicio")), name="agenda_periodo_valido")]
