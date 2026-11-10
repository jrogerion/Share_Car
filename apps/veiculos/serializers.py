from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import FotoVeiculo, Veiculo


class FotoVeiculoSerializer(serializers.ModelSerializer):
    """Representa a foto pública de um veículo com URL absoluta."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = FotoVeiculo
        fields = ("id", "url")

    def get_url(self, foto: FotoVeiculo) -> str:
        url = foto.foto.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class VeiculoPublicoSerializer(serializers.ModelSerializer):
    """Dados públicos do veículo, sem informações do proprietário."""

    fotos = FotoVeiculoSerializer(many=True, read_only=True)

    class Meta:
        model = Veiculo
        fields = (
            "id",
            "categoria",
            "cidade",
            "cambio",
            "combustivel",
            "passageiros",
            "preco_diaria",
            "caracteristicas",
            "fotos",
        )


class BuscaVeiculoQuerySerializer(serializers.Serializer):
    """Valida os filtros de busca recebidos pela API."""

    retirada = serializers.DateField(required=False)
    devolucao = serializers.DateField(required=False)
    cidade = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    categoria = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
    )
    cambio = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
    )
    combustivel = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
    )
    passageiros = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=99,
    )
    diaria_min = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    diaria_max = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    def validate(self, attrs):
        retirada = attrs.get("retirada")
        devolucao = attrs.get("devolucao")

        if bool(retirada) != bool(devolucao):
            raise serializers.ValidationError(
                {
                    "devolucao" if retirada else "retirada": (
                        "Informe a retirada e a devolução juntas."
                    )
                }
            )

        if retirada and devolucao and devolucao <= retirada:
            raise serializers.ValidationError(
                {
                    "devolucao": (
                        "A devolução deve ser posterior à retirada."
                    )
                }
            )

        if retirada and retirada < timezone.localdate():
            raise serializers.ValidationError(
                {"retirada": "A retirada não pode estar no passado."}
            )

        minimo = attrs.get("diaria_min")
        maximo = attrs.get("diaria_max")

        if minimo is not None and maximo is not None and minimo > maximo:
            raise serializers.ValidationError(
                {
                    "diaria_max": (
                        "A diária máxima deve ser maior ou igual à mínima."
                    )
                }
            )

        return attrs
