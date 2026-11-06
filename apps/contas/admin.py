from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html

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
        "documento_para_analise", "cnh_numero", "cnh_validade",
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
        if obj is not None and request.user.is_superuser:
            return tuple(
                ("Análise de documentos", {
                    "description": (
                        "Análise manual, sem consulta a órgãos oficiais. "
                        "Confira os dados antes de aprovar."
                    ),
                    "fields": (
                        "documento_para_analise", "aprovacao_documento",
                        "cnh_numero", "cnh_validade", "aprovacao_cnh",
                    ),
                }) if title == "Aprovações (somente consulta)"
                else (title, options)
                for title, options in fieldsets
            )
        if obj is not None and not request.user.is_superuser:
            return tuple(
                (title, options) for title, options in fieldsets
                if title != "Privilégios administrativos"
            )
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if request.user.is_superuser:
            return tuple(field for field in fields if field not in (
                "aprovacao_documento", "aprovacao_cnh",
            ))
        return fields

    @admin.display(description="Documento de identidade")
    def documento_para_analise(self, obj):
        if not obj.documento_identidade:
            return "Nenhum documento enviado."
        return format_html(
            '<a href="{}">Baixar documento para análise</a>',
            reverse("contas:documento_identidade", args=[obj.pk]),
        )

    def has_change_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser:
            if obj.is_staff or obj.is_superuser:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Bloquear preserva o histórico e os relacionamentos da conta.
        return False
