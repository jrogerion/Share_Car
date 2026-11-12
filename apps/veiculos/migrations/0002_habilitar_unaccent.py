from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("veiculos", "0001_initial"),
    ]

    operations = [
        UnaccentExtension(),
    ]
