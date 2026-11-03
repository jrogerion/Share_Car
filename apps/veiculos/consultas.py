from decimal import Decimal

from django.db.models import QuerySet

from .models import Veiculo


def veiculos_publicos() -> QuerySet[Veiculo]:
    """Retorna apenas veículos que podem ser exibidos publicamente."""
    return Veiculo.objects.filter(
        ativo=True,
        aprovacao=Veiculo.Aprovacao.APROVADO,
        bloqueado=False,
    )


def buscar_veiculos(
    *,
    cidade: str = "",
    categoria: str = "",
    cambio: str = "",
    combustivel: str = "",
    passageiros_min: int | None = None,
    diaria_min: Decimal | None = None,
    diaria_max: Decimal | None = None,
) -> QuerySet[Veiculo]:
    """Aplica os filtros de busca sobre o conjunto de veículos públicos."""
    veiculos = veiculos_publicos()

    if cidade:
        veiculos = veiculos.filter(cidade__icontains=cidade.strip())
    if categoria:
        veiculos = veiculos.filter(categoria__iexact=categoria.strip())
    if cambio:
        veiculos = veiculos.filter(cambio__iexact=cambio.strip())
    if combustivel:
        veiculos = veiculos.filter(combustivel__iexact=combustivel.strip())
    if passageiros_min is not None:
        veiculos = veiculos.filter(passageiros__gte=passageiros_min)
    if diaria_min is not None:
        veiculos = veiculos.filter(preco_diaria__gte=diaria_min)
    if diaria_max is not None:
        veiculos = veiculos.filter(preco_diaria__lte=diaria_max)

    return veiculos.order_by("-id")
