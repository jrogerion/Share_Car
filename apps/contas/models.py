from django.contrib.auth.models import AbstractUser
from django.core.files.storage import storages
from django.db import models
from django.db.models.functions import Lower


def armazenamento_documentos():
    return storages["documentos"]


class LimiteAcesso(models.Model):
    """Contador compartilhado; a chave HMAC não armazena IP ou e-mail em claro."""

    chave = models.CharField(max_length=64, primary_key=True)
    tentativas = models.PositiveIntegerField(default=0)
    expira_em = models.DateTimeField(db_index=True)


class Usuario(AbstractUser):
    class Aprovacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        REJEITADO = "rejeitado", "Rejeitado"

    # Papéis independentes permitem proprietário e locatário simultaneamente.
    # is_staff/permissões representam administração; is_active=False bloqueia a conta.
    proprietario = models.BooleanField(default=False)
    locatario = models.BooleanField(default=False)
    encerrada_em = models.DateTimeField(null=True, blank=True, editable=False)
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

    @property
    def conta_administrativa(self) -> bool:
        return self.is_staff or self.is_superuser

    @property
    def nome_exibicao(self) -> str:
        """Nome público da conta, sem expor o identificador de autenticação."""
        return " ".join(self.get_full_name().split()) or "Usuário"

    def __str__(self) -> str:
        return self.nome_exibicao

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(encerrada_em__isnull=True) | models.Q(is_active=False)
                ),
                name="contas_encerrada_inativa",
            ),
            # Contas antigas sem e-mail continuam válidas até serem atualizadas.
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="contas_usuario_email_unico_ci",
            ),
        ]


class AlteracaoEmail(models.Model):
    """Uma confirmação por conta; nesta tabela fica somente o hash do token."""

    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, primary_key=True,
        related_name="alteracao_email_pendente",
    )
    novo_email = models.EmailField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True)
    assinatura_conta = models.CharField(max_length=64)
    expira_em = models.DateTimeField()
