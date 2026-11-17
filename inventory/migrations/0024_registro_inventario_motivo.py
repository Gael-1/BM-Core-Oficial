import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0023_producto_codigo_barras_alter_producto_sku_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="registro_inventario",
            name="motivo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="inventory.motivo_movimiento",
                verbose_name="Motivo",
            ),
        ),
    ]
