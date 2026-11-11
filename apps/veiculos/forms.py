import warnings
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from django import forms
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps

from .consultas import veiculos_publicos
from .models import FotoVeiculo, Veiculo


class CadastroVeiculoForm(forms.ModelForm):
    passageiros = forms.IntegerField(
        label="Passageiros", min_value=1, max_value=32767,
    )
    preco_diaria = forms.DecimalField(
        label="Diária (R$)", max_digits=10, decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
    )

    class Meta:
        model = Veiculo
        fields = (
            "caracteristicas", "cidade", "categoria", "cambio",
            "combustivel", "passageiros", "preco_diaria",
        )
        labels = {
            "caracteristicas": "Características e descrição do veículo",
            "cidade": "Cidade", "categoria": "Categoria",
            "cambio": "Câmbio", "combustivel": "Combustível",
        }
        help_texts = {
            "caracteristicas": (
                "Informe marca, modelo, estado de conservação e equipamentos."
            ),
            "categoria": "Ex.: Hatch, Sedã ou SUV.",
            "cambio": "Ex.: Manual ou Automático.",
            "combustivel": "Ex.: Flex, Gasolina, Diesel ou Elétrico.",
        }
        widgets = {
            "caracteristicas": forms.Textarea(attrs={"rows": 4}),
            "cidade": forms.TextInput(attrs={
                "autocomplete": "address-level2",
            }),
        }


class EdicaoVeiculoForm(CadastroVeiculoForm):
    ativo = forms.BooleanField(
        label="Manter anúncio ativo", required=False,
        help_text="Um anúncio inativo não aparece na busca pública.",
    )

    class Meta(CadastroVeiculoForm.Meta):
        fields = CadastroVeiculoForm.Meta.fields + ("ativo",)

    def save(self, commit=True):
        veiculo = super().save(commit=False)
        campos = list(self.Meta.fields)
        if set(CadastroVeiculoForm.Meta.fields).intersection(
            self.changed_data,
        ):
            veiculo.aprovacao = Veiculo.Aprovacao.PENDENTE
            campos.append("aprovacao")
        if commit:
            # Não sobrescreve o dono, bloqueios ou decisões não afetadas.
            veiculo.save(update_fields=campos)
        return veiculo


class ImagemVeiculoField(forms.ImageField):
    def to_python(self, data):
        if data and data.size > 5 * 1024 * 1024:
            raise forms.ValidationError("A foto deve ter no máximo 5 MB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            arquivo = super().to_python(data)
        if arquivo:
            if arquivo.image.format not in ("JPEG", "PNG"):
                raise forms.ValidationError(
                    "Envie uma imagem JPEG ou PNG válida.",
                )
            if arquivo.image.width * arquivo.image.height > 20_000_000:
                raise forms.ValidationError(
                    "A foto deve ter até 20 megapixels.",
                )
        return arquivo


class FotoVeiculoForm(forms.ModelForm):
    foto = ImagemVeiculoField(
        label="Foto do veículo",
        help_text="Uma foto por envio, JPEG ou PNG, até 5 MB e 20 megapixels.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )

    class Meta:
        model = FotoVeiculo
        fields = ("foto",)

    def clean_foto(self):
        arquivo = self.cleaned_data["foto"]
        if hasattr(self.files, "getlist") and len(self.files.getlist("foto")) > 1:
            raise forms.ValidationError("Envie uma foto por vez.")
        formato = arquivo.image.format
        buffer = BytesIO()
        arquivo.seek(0)
        try:
            with Image.open(arquivo) as imagem:
                # Corrige a orientação e não publica metadados pessoais/EXIF.
                imagem = ImageOps.exif_transpose(imagem)
                imagem = imagem.convert(
                    "RGB" if formato == "JPEG" else "RGBA",
                )
                imagem.info.clear()
                imagem.save(buffer, format=formato)
        except (OSError, ValueError):
            raise forms.ValidationError("Não foi possível processar a imagem.")
        if buffer.tell() > 5 * 1024 * 1024:
            raise forms.ValidationError("Reduza a foto para até 5 MB.")
        extensao = "jpg" if formato == "JPEG" else "png"
        return ContentFile(buffer.getvalue(), name=f"{uuid4().hex}.{extensao}")


class PeriodoReservaMixin:
    """Valida o período [retirada, devolução) usado na busca e na reserva."""

    def clean_periodo(self):
        if self.errors.get("retirada") or self.errors.get("devolucao"):
            return None, None

        retirada = self.cleaned_data.get("retirada")
        devolucao = self.cleaned_data.get("devolucao")

        if not retirada and not devolucao:
            return retirada, devolucao

        if not retirada or not devolucao:
            campo = "devolucao" if retirada else "retirada"
            self.add_error(campo, "Informe a retirada e a devolução juntas.")
            return retirada, devolucao

        if retirada < timezone.localdate():
            self.add_error("retirada", "A retirada não pode estar no passado.")

        if devolucao <= retirada:
            self.add_error(
                "devolucao",
                "A devolução deve ser posterior à retirada.",
            )

        return retirada, devolucao


class BuscaVeiculoForm(PeriodoReservaMixin, forms.Form):
    """Filtros públicos da busca de veículos."""

    retirada = forms.DateField(
        label="Retirada",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    devolucao = forms.DateField(
        label="Devolução",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    cidade = forms.CharField(
        label="Cidade",
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ex.: São Paulo",
                "autocomplete": "address-level2",
            }
        ),
    )
    categoria = forms.ChoiceField(label="Categoria", required=False)
    cambio = forms.ChoiceField(label="Câmbio", required=False)
    combustivel = forms.ChoiceField(label="Combustível", required=False)
    passageiros = forms.IntegerField(
        label="Capacidade mínima (passageiros)",
        required=False,
        min_value=1,
        max_value=99,
        widget=forms.NumberInput(attrs={"min": 1, "max": 99, "placeholder": "Ex.: 5"}),
    )
    diaria_min = forms.DecimalField(
        label="Diária mínima (R$)",
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={"min": "0.01", "step": "0.01", "placeholder": "Ex.: 100"}
        ),
    )
    diaria_max = forms.DecimalField(
        label="Diária máxima (R$)",
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={"min": "0.01", "step": "0.01", "placeholder": "Ex.: 300"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate().isoformat()
        for campo in ("retirada", "devolucao"):
            self.fields[campo].widget.attrs["min"] = hoje
        publicos = veiculos_publicos()
        self.fields["categoria"].choices = [("", "Todas")] + self._opcoes(
            publicos, "categoria"
        )
        self.fields["cambio"].choices = [("", "Todos")] + self._opcoes(
            publicos, "cambio"
        )
        self.fields["combustivel"].choices = [("", "Todos")] + self._opcoes(
            publicos, "combustivel"
        )
        self._incluir_categoria_solicitada()

    def _incluir_categoria_solicitada(self) -> None:
        """Aceita a categoria de um link direto mesmo sem anúncios publicados."""
        if not self.is_bound:
            return
        categoria = (self.data.get("categoria") or "").strip()
        if not categoria or len(categoria) > 50:
            return
        campo = self.fields["categoria"]
        if categoria not in dict(campo.choices):
            campo.choices = [*campo.choices, (categoria, categoria)]

    def clean(self):
        dados = super().clean()
        self.clean_periodo()
        minimo = dados.get("diaria_min")
        maximo = dados.get("diaria_max")

        if minimo is not None and maximo is not None and minimo > maximo:
            self.add_error(
                "diaria_max",
                "A diária máxima deve ser maior ou igual à mínima.",
            )

        return dados

    @staticmethod
    def _opcoes(veiculos, campo: str) -> list[tuple[str, str]]:
        valores = (
            veiculos.exclude(**{campo: ""})
            .values_list(campo, flat=True)
            .distinct()
            .order_by(campo)
        )
        return [(valor, valor) for valor in valores]
