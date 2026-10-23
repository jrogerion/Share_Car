from django.db import models
from django.db.models import F, Q


class Pagamento(models.Model):
    class Meio(models.TextChoices):
        PIX = "pix", "Pix"
        CARTAO = "cartao", "Cartão"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Recusado"
        ESTORNADO = "estornado", "Estornado"

    # MVP: um pagamento simulado por reserva; novas tentativas atualizam o mesmo registro.
    reserva = models.OneToOneField("reservas.Reserva", on_delete=models.PROTECT, related_name="pagamento")
    meio = models.CharField(max_length=6, choices=Meio.choices)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDENTE)
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    comissao = models.DecimalField(max_digits=12, decimal_places=2)
    repasse_proprietario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "pagamentos"
        constraints = [
            models.CheckConstraint(condition=Q(valor_bruto__gte=0, comissao__gte=0, repasse_proprietario__gte=0), name="pagamento_valores_validos"),
            # Taxas não têm destinatário especificado: integram o bruto e o saldo repassado.
            models.CheckConstraint(condition=Q(valor_bruto=F("comissao") + F("repasse_proprietario")), name="pagamento_soma_consistente"),
        ]
