from django.db import migrations

ITEMS = [
    ("Movimientos", "inventory:historial", "clock-rotate-left", 90),
    ("Registrar movimiento", "inventory:movimiento", "arrow-right-arrow-left", 91),
    ("Categorías", "categorias:index", "tags", 92),
]


def agregar(apps, schema_editor):
    Menu = apps.get_model("navigation", "Menu")
    padre = Menu.objects.filter(parent__isnull=True, nombre__icontains="inventario").first()
    for nombre, url, icono, orden in ITEMS:
        if not Menu.objects.filter(url=url).exists():
            Menu.objects.create(nombre=nombre, url=url, icono=icono, orden=orden, parent=padre)


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(agregar, migrations.RunPython.noop),
    ]
