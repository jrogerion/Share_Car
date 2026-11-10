from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import AlteracaoUsuarioAdminForm, CriacaoUsuarioAdminForm
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = AlteracaoUsuarioAdminForm
    add_form = CriacaoUsuarioAdminForm
    list_display = (
        "email", "first_name", "last_name", "proprietario", "locatario",
        "is_active", "is_staff", "aprovacao_documento", "aprovacao_cnh",
    )
    list_filter = (
        "proprietario", "locatario", "is_active", "is_staff",
        "aprovacao_documento", "aprovacao_cnh",
    )
    search_fields = ("first_name", "last_name", "email", "username")
    ordering = ("email", "pk")
    readonly_fields = (
        "last_login", "date_joined", "aprovacao_documento", "aprovacao_cnh",
    )
    fieldsets = (
        ("Acesso", {"fields": ("username", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "last_name", "email")}),
        ("Perfis de uso", {"fields": ("proprietario", "locatario")}),
        ("Situação da conta", {"fields": ("is_active",)}),
        ("Aprovações (somente consulta)", {
            "fields": ("aprovacao_documento", "aprovacao_cnh"),
        }),
        ("Privilégios administrativos", {
            "fields": (
                "is_staff", "is_superuser", "groups", "user_permissions",
            ),
        }),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        ("Acesso", {
            "classes": ("wide",),
            "fields": (
                "username", "email", "usable_password",
                "password1", "password2",
            ),
        }),
        ("Dados pessoais", {"fields": ("first_name", "last_name")}),
        ("Perfis de uso", {"fields": ("proprietario", "locatario")}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            # Evita acesso também por URLs diretas e pela troca de senha.
            queryset = queryset.filter(is_staff=False, is_superuser=False)
        return queryset

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None and not request.user.is_superuser:
            return tuple(
                (title, options) for title, options in fieldsets
                if title != "Privilégios administrativos"
            )
        return fieldsets

    def has_change_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser:
            if obj.is_staff or obj.is_superuser:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Bloquear preserva o histórico e os relacionamentos da conta.
        return False
