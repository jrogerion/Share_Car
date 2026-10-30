from uuid import uuid4

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario


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
