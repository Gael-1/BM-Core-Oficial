from django.db import migrations

MOTIVOS = [
    ("Compra", "Recepción de mercancía de un proveedor"),
    ("Venta", "Salida por venta o entrega a cliente"),
    ("Merma", "Pérdida, daño o caducidad"),
    ("Ajuste de inventario", "Corrección tras un conteo físico"),
    ("Devolución", "Devolución a proveedor o de un cliente"),
    ("Consumo interno", "Material usado por la propia operación"),
]


def crear_motivos(apps, schema_editor):
    Motivo = apps.get_model("inventory", "motivo_movimiento")
    for nombre, descripcion in MOTIVOS:
        Motivo.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0024_registro_inventario_motivo"),
    ]

    operations = [
        migrations.RunPython(crear_motivos, migrations.RunPython.noop),
    ]
