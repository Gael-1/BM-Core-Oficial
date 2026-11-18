from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compra", "0003_ordendecompra_estatus"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordendecompra",
            name="autorizada_por_regla",
            field=models.BooleanField(default=False, verbose_name="Autorizada automáticamente por regla"),
        ),
        migrations.CreateModel(
            name="ConfiguracionCompras",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("autoautorizar", models.BooleanField(default=False, verbose_name="Autorizar automáticamente las órdenes pequeñas")),
                ("monto_maximo", models.DecimalField(
                    decimal_places=2, default=0, max_digits=12,
                    help_text="Las órdenes con total menor o igual a este monto se autorizan al crearse.",
                    verbose_name="Monto máximo para autorizar solas")),
            ],
            options={"verbose_name": "Configuración de compras", "verbose_name_plural": "Configuración de compras"},
        ),
    ]
