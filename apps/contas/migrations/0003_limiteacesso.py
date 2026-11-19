from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0002_usuario_email_unico"),
    ]

    operations = [
        migrations.CreateModel(
            name="LimiteAcesso",
            fields=[
                ("chave", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("tentativas", models.PositiveIntegerField(default=0)),
                ("expira_em", models.DateTimeField(db_index=True)),
            ],
        ),
    ]
