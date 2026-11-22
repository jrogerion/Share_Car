from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0003_limiteacesso"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlteracaoEmail",
            fields=[
                ("usuario", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, related_name="alteracao_email_pendente",
                    serialize=False, to=settings.AUTH_USER_MODEL,
                )),
                ("novo_email", models.EmailField(max_length=254)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("assinatura_conta", models.CharField(max_length=64)),
                ("expira_em", models.DateTimeField()),
            ],
        ),
    ]
