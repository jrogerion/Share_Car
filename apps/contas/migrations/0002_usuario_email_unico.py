from django.db import migrations, models
from django.db.models.functions import Lower


def verificar_emails_duplicados(apps, schema_editor):
    usuario = apps.get_model("contas", "Usuario")
    duplicados = (
        usuario.objects.using(schema_editor.connection.alias)
        .exclude(email="")
        .annotate(email_normalizado=Lower("email"))
        .values("email_normalizado")
        .annotate(total=models.Count("pk"))
        .filter(total__gt=1)
    )
    if duplicados.exists():
        raise RuntimeError(
            "Existem usuários com e-mails duplicados. Revise as contas antes "
            "de aplicar esta migration. Nenhuma conta foi alterada."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            verificar_emails_duplicados, migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="usuario",
            constraint=models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="contas_usuario_email_unico_ci",
            ),
        ),
    ]
