import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("proveedores", "0010_catalogo_regimen_fiscal"),
        ("ventas", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cliente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=150, verbose_name="Nombre comercial")),
                ("razon_social", models.CharField(max_length=200, verbose_name="Razón social")),
                ("rfc", models.CharField(max_length=13, verbose_name="RFC")),
                ("codigo_postal", models.CharField(max_length=5, verbose_name="Código postal fiscal")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Correo")),
                ("uso_cfdi", models.CharField(
                    choices=[("G01", "G01 · Adquisición de mercancías"), ("G03", "G03 · Gastos en general"),
                             ("I04", "I04 · Equipo de cómputo y accesorios"), ("S01", "S01 · Sin efectos fiscales")],
                    default="G03", max_length=3, verbose_name="Uso del CFDI")),
                ("activo", models.BooleanField(default=True)),
                ("regimen_fiscal", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    to="proveedores.regimenfiscal", verbose_name="Régimen fiscal")),
            ],
            options={"verbose_name": "Cliente", "verbose_name_plural": "Clientes", "ordering": ["nombre"]},
        ),
        migrations.AddField(
            model_name="venta",
            name="cliente",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="ventas", to="ventas.cliente", verbose_name="Cliente fiscal"),
        ),
        migrations.CreateModel(
            name="Prefactura",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.CharField(max_length=20, unique=True)),
                ("creada", models.DateTimeField(auto_now_add=True)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                ("iva", models.DecimalField(decimal_places=2, max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("datos", models.JSONField()),
                ("creada_por", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="prefacturas", to=settings.AUTH_USER_MODEL)),
                ("venta", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT, related_name="prefactura", to="ventas.venta")),
            ],
            options={"verbose_name": "Prefactura", "verbose_name_plural": "Prefacturas", "ordering": ["-creada"]},
        ),
    ]
