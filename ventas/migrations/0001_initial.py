import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0029_alertastock"),
        ("negocio", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Venta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("folio", models.CharField(max_length=30, unique=True, verbose_name="Folio")),
                ("cliente_nombre", models.CharField(blank=True, max_length=150, verbose_name="Cliente")),
                ("referencia_externa", models.CharField(
                    blank=True, null=True, max_length=80, unique=True, verbose_name="Referencia externa",
                    help_text="Identificador de la venta en el sistema de origen; evita registrarla dos veces.")),
                ("origen", models.CharField(
                    choices=[("web", "Captura en el sistema"), ("api", "Sistema externo (API)")],
                    default="web", max_length=10)),
                ("estatus", models.CharField(
                    choices=[("completada", "Completada"), ("cancelada", "Cancelada")],
                    default="completada", max_length=12)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("comentarios", models.CharField(blank=True, max_length=255)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("cancelada_en", models.DateTimeField(blank=True, null=True)),
                ("almacen", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="ventas",
                    to="inventory.almacen", verbose_name="Almacén de salida")),
                ("cancelada_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ventas_canceladas", to=settings.AUTH_USER_MODEL)),
                ("negocio", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to="negocio.negocio", verbose_name="Negocio")),
                ("usuario", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ventas_registradas", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Venta", "verbose_name_plural": "Ventas", "ordering": ["-fecha", "-pk"]},
        ),
        migrations.CreateModel(
            name="LineaVenta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cantidad", models.FloatField()),
                ("precio_unitario", models.DecimalField(decimal_places=2, max_digits=12)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                ("producto", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="lineas_venta",
                    to="inventory.producto")),
                ("venta", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="lineas", to="ventas.venta")),
            ],
            options={"verbose_name": "Línea de venta", "verbose_name_plural": "Líneas de venta"},
        ),
    ]
