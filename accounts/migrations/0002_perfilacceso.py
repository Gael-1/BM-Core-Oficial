import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerfilAcceso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("descripcion", models.CharField(blank=True, max_length=200)),
                ("inventario", models.BooleanField(default=False, verbose_name="Inventario (productos, movimientos, traspasos, recepción)")),
                ("compras", models.BooleanField(default=False, verbose_name="Compras (proveedores y órdenes de compra)")),
                ("ventas", models.BooleanField(default=False, verbose_name="Ventas (registrar ventas, clientes y prefacturas)")),
                ("administrar", models.BooleanField(default=False, verbose_name="Administración (autorizar compras, negocios, usuarios, API)")),
                ("grupo", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="perfil_acceso", to="auth.group")),
            ],
            options={"ordering": ["grupo__name"]},
        ),
    ]
