from rest_framework import generics
from rest_framework.pagination import PageNumberPagination

from .consultas import buscar_veiculos, com_fotos_ordenadas, veiculos_publicos
from .serializers import BuscaVeiculoQuerySerializer, VeiculoPublicoSerializer


class VeiculoPagination(PageNumberPagination):
    """Paginação da listagem pública de veículos."""

    page_size = 6
    page_size_query_param = "page_size"
    max_page_size = 50


class VeiculoListAPIView(generics.ListAPIView):
    """Lista veículos públicos, aplicando os filtros combinados da busca."""

    serializer_class = VeiculoPublicoSerializer
    pagination_class = VeiculoPagination

    def get_queryset(self):
        filtro = BuscaVeiculoQuerySerializer(data=self.request.query_params)
        filtro.is_valid(raise_exception=True)
        dados = filtro.validated_data

        return com_fotos_ordenadas(
            buscar_veiculos(
                cidade=dados.get("cidade", ""),
                categoria=dados.get("categoria", ""),
                cambio=dados.get("cambio", ""),
                combustivel=dados.get("combustivel", ""),
                passageiros_min=dados.get("passageiros"),
                diaria_min=dados.get("diaria_min"),
                diaria_max=dados.get("diaria_max"),
                inicio=dados.get("retirada"),
                fim=dados.get("devolucao"),
            )
        )


class VeiculoDetailAPIView(generics.RetrieveAPIView):
    """Exibe um veículo público; veículos não públicos resultam em 404."""

    serializer_class = VeiculoPublicoSerializer

    def get_queryset(self):
        return com_fotos_ordenadas(veiculos_publicos())
