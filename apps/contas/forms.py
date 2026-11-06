import warnings
from uuid import uuid4

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.utils import timezone
from PIL import Image

from .models import Usuario


class EmailUnicoAdminMixin:
    """Valida e-mails no Admin, preservando contas antigas sem endereço."""

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower()
        if email and Usuario.objects.filter(email__iexact=email).exclude(
            pk=self.instance.pk,
        ).exists():
            raise forms.ValidationError(
                "Não é possível cadastrar este e-mail.",
            )
        return email


class CriacaoUsuarioAdminForm(EmailUnicoAdminMixin, AdminUserCreationForm):
    email = forms.EmailField(label="E-mail", max_length=254)

    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = (
            "username", "email", "first_name", "last_name",
            "proprietario", "locatario",
        )


class AlteracaoUsuarioAdminForm(EmailUnicoAdminMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"

    def clean(self):
        dados = super().clean()
        if dados.get("aprovacao_documento") == Usuario.Aprovacao.APROVADO:
            documento = self.instance.documento_identidade
            if not documento or not documento.storage.exists(documento.name):
                self.add_error(
                    "aprovacao_documento",
                    "Não é possível aprovar sem um documento disponível.",
                )
        if dados.get("aprovacao_cnh") == Usuario.Aprovacao.APROVADO:
            if (not self.instance.cnh_numero.strip() or
                    not self.instance.cnh_validade):
                self.add_error(
                    "aprovacao_cnh", "Informe número e validade da CNH no perfil.",
                )
            elif self.instance.cnh_validade < timezone.localdate():
                self.add_error(
                    "aprovacao_cnh", "Não é possível aprovar uma CNH vencida.",
                )
        return dados


class ImagemDocumentoField(forms.ImageField):
    def to_python(self, data):
        if data and data.size > 5 * 1024 * 1024:
            raise forms.ValidationError("O arquivo deve ter no máximo 5 MB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            arquivo = super().to_python(data)
        if arquivo and arquivo.image.format not in ("JPEG", "PNG"):
            raise forms.ValidationError("Envie uma imagem JPEG ou PNG válida.")
        return arquivo


class DocumentoIdentidadeForm(forms.ModelForm):
    documento_identidade = ImagemDocumentoField(
        label="Documento de identidade",
        help_text=(
            "JPEG ou PNG, até 5 MB. "
            "Use somente documentos fictícios nos testes."
        ),
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )

    class Meta:
        model = Usuario
        fields = ("documento_identidade",)

    def clean_documento_identidade(self):
        if not self.files.get("documento_identidade"):
            raise forms.ValidationError(
                "Selecione uma nova imagem para enviar.",
            )
        arquivo = self.cleaned_data["documento_identidade"]
        extensao = "jpg" if arquivo.image.format == "JPEG" else "png"
        # Não inclui nomes pessoais nem caminhos fornecidos pelo cliente.
        arquivo.name = f"{uuid4().hex}.{extensao}"
        return arquivo

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.aprovacao_documento = Usuario.Aprovacao.PENDENTE
        if commit:
            usuario.save(update_fields=[
                "documento_identidade", "aprovacao_documento",
            ])
        return usuario


class PerfilUsuarioForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Nome", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Sobrenome", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )

    class Meta:
        model = Usuario
        fields = (
            "first_name", "last_name", "locatario", "proprietario",
            "cnh_numero", "cnh_validade",
        )
        labels = {
            "locatario": "Quero alugar carros",
            "proprietario": "Quero anunciar meu carro",
            "cnh_numero": "Número da CNH",
            "cnh_validade": "Validade da CNH",
        }
        widgets = {
            "cnh_numero": forms.TextInput(attrs={"autocomplete": "off"}),
            "cnh_validade": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get("locatario") or
                cleaned_data.get("proprietario")):
            raise forms.ValidationError("Selecione pelo menos um perfil de uso.")
        numero = cleaned_data.get("cnh_numero")
        validade = cleaned_data.get("cnh_validade")
        if numero and not validade and "cnh_validade" not in self.errors:
            self.add_error("cnh_validade", "Informe a validade da CNH.")
        if validade and not numero:
            self.add_error("cnh_numero", "Informe o número da CNH.")
        return cleaned_data

    def save(self, commit=True):
        usuario = super().save(commit=False)
        campos = list(self.Meta.fields)
        if {"cnh_numero", "cnh_validade"}.intersection(self.changed_data):
            usuario.aprovacao_cnh = Usuario.Aprovacao.PENDENTE
            campos.append("aprovacao_cnh")
        if commit:
            # Não sobrescreve senha, e-mail ou privilégios fora deste formulário.
            usuario.save(update_fields=campos)
        return usuario


class LoginEmailForm(AuthenticationForm):
    # Mantém o nome esperado pela AuthenticationForm, mas valida como e-mail.
    username = forms.EmailField(
        label="E-mail", max_length=254,
        widget=forms.EmailInput(attrs={
            "autofocus": True, "autocomplete": "username",
        }),
    )
    error_messages = {
        "invalid_login": "E-mail ou senha inválidos.",
        "inactive": "E-mail ou senha inválidos.",
    }

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(
                self.request, email=email, password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class CadastroUsuarioForm(UserCreationForm):
    email = forms.EmailField(
        label="E-mail", max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    first_name = forms.CharField(
        label="Nome", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Sobrenome", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    locatario = forms.BooleanField(
        label="Quero alugar carros", required=False, initial=True,
    )
    proprietario = forms.BooleanField(
        label="Quero anunciar meu carro", required=False,
    )

    class Meta:
        model = Usuario
        fields = (
            "first_name", "last_name", "email", "locatario", "proprietario",
            "password1", "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Não é possível cadastrar este e-mail.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get("locatario") or cleaned_data.get("proprietario")):
            raise forms.ValidationError("Selecione pelo menos um perfil de uso.")
        return cleaned_data

    def save(self, commit=True):
        usuario = super().save(commit=False)
        # Mantém compatibilidade com contas existentes sem pedir username no site.
        usuario.username = uuid4().hex
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario
