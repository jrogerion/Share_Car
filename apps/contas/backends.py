from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Autentica o site por e-mail e preserva username para o Django Admin."""

    def authenticate(
        self, request, username=None, password=None, email=None, **kwargs,
    ):
        if email is None:
            return super().authenticate(request, username, password, **kwargs)
        if not email.strip() or password is None:
            return None

        usuario_model = get_user_model()
        try:
            usuario = usuario_model.objects.get(email__iexact=email.strip())
        except (usuario_model.DoesNotExist, usuario_model.MultipleObjectsReturned):
            # Mantém o custo do hash mesmo quando não há uma conta elegível.
            usuario_model().set_password(password)
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
