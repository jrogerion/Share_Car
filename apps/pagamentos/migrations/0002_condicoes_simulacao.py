from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pagamentos", "0001_initial")]

    operations = [
        migrations.AddField(model_name="pagamento", name="parcelas", field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name="pagamento", name="juros", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name="pagamento", name="desconto", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddConstraint(model_name="pagamento", constraint=models.CheckConstraint(condition=models.Q(parcelas__gte=1, parcelas__lte=8), name="pagamento_parcelas_validas")),
        migrations.AddConstraint(model_name="pagamento", constraint=models.CheckConstraint(condition=models.Q(juros__gte=0, desconto__gte=0, desconto__lte=models.F("valor_bruto")) & (models.Q(juros=0) | models.Q(desconto=0)), name="pagamento_ajustes_validos")),
        migrations.AddConstraint(model_name="pagamento", constraint=models.CheckConstraint(condition=~models.Q(meio="pix") | models.Q(parcelas=1), name="pagamento_pix_a_vista")),
    ]
