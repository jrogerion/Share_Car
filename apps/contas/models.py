from django.contrib.auth.models import AbstractUser
from django.core.files.storage import storages
from django.db import models


def armazenamento_documentos():
    return storages["documentos"]


class Usuario(AbstractUser):
    class Aprovacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        REJEITADO = "rejeitado", "Rejeitado"

    # Papéis independentes permitem proprietário e locatário simultaneamente.
    # is_staff/permissões representam administração; is_active=False bloqueia a conta.
    proprietario = models.BooleanField(default=False)
    locatario = models.BooleanField(default=False)
    documento_identidade = models.FileField(
        upload_to="identidades/", storage=armazenamento_documentos, blank=True,
    )
    aprovacao_documento = models.CharField(
        max_length=10, choices=Aprovacao.choices, default=Aprovacao.PENDENTE,
    )
    # O documento não detalha dados da CNH: adotados número e validade, sem unicidade presumida.
    cnh_numero = models.CharField(max_length=20, blank=True)
    cnh_validade = models.DateField(null=True, blank=True)
    aprovacao_cnh = models.CharField(
        max_length=10, choices=Aprovacao.choices, default=Aprovacao.PENDENTE,
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
