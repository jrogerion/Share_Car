from decimal import ROUND_HALF_UP, Decimal

from django.utils.formats import number_format


def distribuir_parcelas(total: Decimal, quantidade: int) -> list[Decimal]:
    """Distribui o resto em centavos sem alterar a soma contratada."""
    centavos = int(total * 100)
    valor, resto = divmod(centavos, quantidade)
    return [
        Decimal(valor + (indice < resto)) / 100
        for indice in range(quantidade)
    ]


def resumo_parcelas(total: Decimal, quantidade: int) -> str:
    valores = distribuir_parcelas(total, quantidade)
    grupos = []
    for valor in dict.fromkeys(valores):
        moeda = number_format(valor, decimal_pos=2, force_grouping=True)
        grupos.append(f"{valores.count(valor)}x de R$ {moeda}")
    return " + ".join(grupos)


def calcular_condicoes(total: Decimal, meio: str, parcelas: int = 1) -> dict:
    if meio not in ("pix", "cartao"):
        raise ValueError("Meio de pagamento inválido.")
    if type(parcelas) is not int or not 1 <= parcelas <= 8:
        raise ValueError("Escolha de 1 a 8 parcelas.")
    if meio == "pix" and parcelas != 1:
        raise ValueError("O Pix deve ser pago à vista.")
    taxa = parcelas if meio == "cartao" and parcelas > 6 else 0
    juros = (total * Decimal(taxa) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )
    desconto = Decimal("0.00")
    if meio == "pix":
        desconto = (total * Decimal("0.05")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
    final = total + juros - desconto
    return {
        "meio": meio, "parcelas": parcelas, "taxa": taxa,
        "juros": juros, "desconto": desconto, "total": final,
        "resumo": resumo_parcelas(final, parcelas),
    }
