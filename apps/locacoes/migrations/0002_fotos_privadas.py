import apps.locacoes.storage
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("locacoes", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="fotoregistrolocacao", name="foto",
            field=models.ImageField(
                storage=apps.locacoes.storage.armazenamento_vistorias,
                upload_to="locacoes/",
            ),
        ),
    ]
