from django.db import models
from django.db.models import Q


class ConfiguracaoComissao(models.Model):
    # Uma configuração global; CHECK + PK permitem no máximo uma linha.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    percentual = models.DecimalField(max_digits=5, decimal_places=2, default=15)

    class Meta:
        verbose_name = "configuração de comissão"
        verbose_name_plural = "configuração de comissão"
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="comissao_config_unica"),
            models.CheckConstraint(condition=Q(percentual__gte=0, percentual__lte=100), name="comissao_percentual_valido"),
        ]
