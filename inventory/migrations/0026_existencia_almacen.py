import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0025_motivos_iniciales"),
    ]

    operations = [
        migrations.CreateModel(
            name="Existencia_Almacen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cantidad", models.FloatField(default=0, verbose_name="Cantidad")),
                ("modificado", models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificado")),
                (
                    "almacen",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="existencias",
                        to="inventory.almacen",
                        verbose_name="Almacén",
                    ),
                ),
                (
                    "inventario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="existencias",
                        to="inventory.inventario_producto",
                        verbose_name="Inventario",
                    ),
                ),
            ],
            options={
                "verbose_name": "Existencia por almacén",
                "verbose_name_plural": "Existencias por almacén",
            },
        ),
        migrations.AddConstraint(
            model_name="existencia_almacen",
            constraint=models.UniqueConstraint(
                fields=("inventario", "almacen"), name="uniq_existencia_inventario_almacen"
            ),
        ),
    ]
