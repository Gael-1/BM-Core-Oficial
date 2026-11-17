from django.db import migrations

# (nombre, abreviatura, permite_decimales)
MEDIDAS = [
    ("Pieza", "pza", False),
    ("Caja", "caja", False),
    ("Paquete", "paq", False),
    ("Kilogramo", "kg", True),
    ("Gramo", "g", True),
    ("Litro", "L", True),
    ("Mililitro", "ml", True),
    ("Metro", "m", True),
]


def cargar(apps, schema_editor):
    Medida = apps.get_model("inventory", "Medidas_Inventario")
    for nombre, abreviatura, decimales in MEDIDAS:
        Medida.objects.get_or_create(
            nombre=nombre, defaults={"abreviatura": abreviatura, "permite_decimales": decimales}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0027_existencias_iniciales"),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
