from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import FileExtensionValidator

from .models import Usuario

TAMANHO_MAXIMO_DOCUMENTO = 5 * 1024 * 1024
EXTENSOES_DOCUMENTO = ["pdf", "jpg", "jpeg", "png"]
TIPOS_DOCUMENTO = {"application/pdf", "image/jpeg", "image/png"}

PAPEIS = (
    ("locatario", "Quero alugar veículos"),
    ("proprietario", "Quero anunciar meu veículo"),
)


def _sincronizar_papeis(usuario: Usuario, papeis) -> None:
    """Grava os papéis escolhidos mantendo a possibilidade de acumulá-los."""
    usuario.locatario = "locatario" in papeis
    usuario.proprietario = "proprietario" in papeis


class EntrarForm(AuthenticationForm):
    """Formulário de login com atributos de autocompletar do navegador."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password"}
        )


class CadastroForm(UserCreationForm):
    """Cria uma conta com e-mail obrigatório e pelo menos um papel."""

    email = forms.EmailField(label="E-mail")
    papeis = forms.MultipleChoiceField(
        label="Como você vai usar o ShareCar?",
        choices=PAPEIS,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Escolha pelo menos uma forma de usar o ShareCar.",
        },
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["first_name"].label = "Nome"
        self.fields["last_name"].label = "Sobrenome"
        self.fields["username"].help_text = (
            "Use letras, números e os caracteres @/./+/-/_."
        )
        self.fields["password1"].help_text = (
            "Use pelo menos 8 caracteres, evitando senhas comuns ou apenas números."
        )
        self.fields["password2"].help_text = "Repita a senha para confirmação."
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self) -> str:
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Já existe uma conta com este e-mail."
            )
        return email

    def save(self, commit=True) -> Usuario:
        usuario = super().save(commit=False)
        _sincronizar_papeis(usuario, self.cleaned_data["papeis"])
        if commit:
            usuario.save()
        return usuario


class PerfilForm(forms.ModelForm):
    """Atualiza dados pessoais, papéis, CNH e documento privado."""

    papeis = forms.MultipleChoiceField(
        label="Como você usa o ShareCar?",
        choices=PAPEIS,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Escolha pelo menos uma forma de usar o ShareCar.",
        },
    )

    class Meta:
        model = Usuario
        fields = (
            "first_name",
            "last_name",
            "email",
            "cnh_numero",
            "cnh_validade",
            "documento_identidade",
        )
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "email": "E-mail",
            "cnh_numero": "Número da CNH",
            "cnh_validade": "Validade da CNH",
            "documento_identidade": "Documento de identidade",
        }
        widgets = {
            "cnh_validade": forms.DateInput(attrs={"type": "date"}),
            # Não exibe o nome nem a URL do arquivo já armazenado.
            "documento_identidade": forms.FileInput,
        }
        help_texts = {
            "documento_identidade": (
                "Envie um arquivo PDF, JPG ou PNG de até 5 MB. "
                "O documento fica em armazenamento privado e não é publicado no anúncio."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["papeis"].initial = self._papeis_atuais()
        self.fields["documento_identidade"].required = False
        self.fields["documento_identidade"].validators.append(
            FileExtensionValidator(EXTENSOES_DOCUMENTO)
        )
        self.fields["documento_identidade"].widget.attrs["accept"] = (
            ".pdf,.jpg,.jpeg,.png"
        )
        self.fields["cnh_numero"].widget.attrs["autocomplete"] = "off"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"

    def _papeis_atuais(self) -> list[str]:
        if not self.instance.pk:
            return []
        return [
            papel
            for papel in ("locatario", "proprietario")
            if getattr(self.instance, papel)
        ]

    def clean_email(self) -> str:
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Informe um e-mail para acessar a conta.")
        contas = Usuario.objects.filter(email__iexact=email)
        if self.instance.pk:
            contas = contas.exclude(pk=self.instance.pk)
        if contas.exists():
            raise forms.ValidationError(
                "Já existe uma conta com este e-mail."
            )
        return email

    def clean_papeis(self) -> list[str]:
        papeis = self.cleaned_data.get("papeis") or []
        if self.instance.pk:
            if self.instance.veiculos.exists() and "proprietario" not in papeis:
                raise forms.ValidationError(
                    "Você possui veículos cadastrados; mantenha o perfil de proprietário."
                )
            if self.instance.reservas.exists() and "locatario" not in papeis:
                raise forms.ValidationError(
                    "Você possui reservas como locatário; mantenha esse perfil."
                )
        return papeis

    def clean_documento_identidade(self):
        arquivo = self.cleaned_data.get("documento_identidade")
        if not arquivo:
            return arquivo

        if arquivo.size > TAMANHO_MAXIMO_DOCUMENTO:
            raise forms.ValidationError(
                "O documento deve ter no máximo 5 MB."
            )

        tipo = getattr(arquivo, "content_type", None)
        if tipo and tipo not in TIPOS_DOCUMENTO:
            raise forms.ValidationError(
                "Envie o documento em PDF, JPG ou PNG."
            )
        return arquivo

    def clean(self):
        dados = super().clean()
        numero = (dados.get("cnh_numero") or "").strip()
        validade = dados.get("cnh_validade")

        if bool(numero) != bool(validade):
            raise forms.ValidationError(
                "Informe o número e a validade da CNH juntos."
            )

        dados["cnh_numero"] = numero
        return dados

    def save(self, commit=True) -> Usuario:
        usuario = super().save(commit=False)
        _sincronizar_papeis(usuario, self.cleaned_data["papeis"])

        alteracoes = set(self.changed_data)
        if "documento_identidade" in alteracoes:
            usuario.aprovacao_documento = Usuario.Aprovacao.PENDENTE
        if {"cnh_numero", "cnh_validade"} & alteracoes:
            usuario.aprovacao_cnh = Usuario.Aprovacao.PENDENTE

        if commit:
            usuario.save()
            self.save_m2m()
        return usuario
