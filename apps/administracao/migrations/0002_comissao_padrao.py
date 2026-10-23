from django.db import migrations


def criar_comissao_padrao(apps, schema_editor):
    configuracao = apps.get_model("administracao", "ConfiguracaoComissao")
    configuracao.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1, defaults={"percentual": "15.00"},
    )


class Migration(migrations.Migration):
    dependencies = [("administracao", "0001_initial")]
    operations = [migrations.RunPython(criar_comissao_padrao, migrations.RunPython.noop)]
