from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Round

from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva


def indicadores_financeiros(reservas):
    """Agrega snapshots contratados, nunca a comissão global atual."""
    pagamentos = Pagamento.objects.filter(reserva__in=reservas)
    final = F("valor_bruto") + F("juros") - F("desconto")
    aprovados = pagamentos.filter(status=Pagamento.Status.APROVADO)
    financeiro = aprovados.aggregate(
        comissao=Sum("comissao", default=Decimal("0")),
        total_aprovado=Sum(final, default=Decimal("0")),
        juros=Sum("juros", default=Decimal("0")),
        descontos=Sum("desconto", default=Decimal("0")),
        repasses=Sum("repasse_proprietario", default=Decimal("0")),
    )
    financeiro["estornos"] = pagamentos.filter(
        status=Pagamento.Status.ESTORNADO,
    ).aggregate(total=Sum(final, default=Decimal("0")))["total"]
    comissao_prevista = Round(ExpressionWrapper(
        F("total") * F("percentual_comissao") / Decimal("100"),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    ), precision=2)
    financeiro["prevista"] = reservas.filter(
        status=Reserva.Status.ACEITA,
    ).exclude(pagamento__status=Pagamento.Status.APROVADO).aggregate(
        total=Sum(comissao_prevista, default=Decimal("0")),
    )["total"]

    contagens = dict(reservas.order_by().values_list("status").annotate(total=Count("pk")))
    total_reservas = sum(contagens.values())
    status = [
        {"nome": nome, "total": contagens.get(valor, 0),
         "percentual": round(contagens.get(valor, 0) * 100 / total_reservas) if total_reservas else 0}
        for valor, nome in Reserva.Status.choices
    ]
    contagens_meios = dict(aprovados.order_by().values_list("meio").annotate(total=Count("pk")))
    total_pagamentos = sum(contagens_meios.values())
    meios = [
        {"nome": nome, "total": contagens_meios.get(valor, 0),
         "percentual": round(contagens_meios.get(valor, 0) * 100 / total_pagamentos) if total_pagamentos else 0}
        for valor, nome in Pagamento.Meio.choices
    ]
    return {
        "financeiro": financeiro, "grafico_status": status,
        "grafico_meios": meios, "total_reservas_dashboard": total_reservas,
        "total_pagamentos_dashboard": total_pagamentos,
    }
