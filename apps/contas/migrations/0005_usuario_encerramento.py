from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0004_alteracaoemail"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario", name="encerrada_em",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="usuario",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(encerrada_em__isnull=True) | models.Q(is_active=False)
                ),
                name="contas_encerrada_inativa",
            ),
        ),
    ]
