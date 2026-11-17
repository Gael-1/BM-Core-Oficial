from django.db import migrations


def repartir_existencias(apps, schema_editor):
    """Cada existencia actual con almacén pasa a ser la fila de ese almacén."""
    Inventario = apps.get_model("inventory", "Inventario_Producto")
    Existencia = apps.get_model("inventory", "Existencia_Almacen")
    for inventario in Inventario.objects.filter(almacen__isnull=False, cantidad__gt=0):
        Existencia.objects.get_or_create(
            inventario=inventario,
            almacen_id=inventario.almacen_id,
            defaults={"cantidad": inventario.cantidad},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0026_existencia_almacen"),
    ]

    operations = [
        migrations.RunPython(repartir_existencias, migrations.RunPython.noop),
    ]
