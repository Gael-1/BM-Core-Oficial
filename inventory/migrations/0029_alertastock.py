import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0028_medidas_iniciales"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertaStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notificado", models.DateTimeField(blank=True, null=True, verbose_name="Último aviso enviado")),
                ("cantidad_al_notificar", models.FloatField(blank=True, null=True)),
                (
                    "producto",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alerta_stock",
                        to="inventory.producto",
                        verbose_name="Producto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Alerta de stock",
                "verbose_name_plural": "Alertas de stock",
            },
        ),
    ]
