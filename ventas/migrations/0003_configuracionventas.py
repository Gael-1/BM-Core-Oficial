from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0002_clientes_y_prefacturas"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionVentas",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prefactura_automatica", models.BooleanField(
                    default=False,
                    help_text="Solo aplica a ventas con un cliente del catálogo (con RFC y datos fiscales completos).",
                    verbose_name="Generar la prefactura automáticamente al registrar la venta")),
            ],
            options={"verbose_name": "Configuración de ventas", "verbose_name_plural": "Configuración de ventas"},
        ),
    ]
