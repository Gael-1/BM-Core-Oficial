from django.db import migrations


def agregar(apps, schema_editor):
    Menu = apps.get_model("navigation", "Menu")
    if Menu.objects.filter(url="inventory:pronostico").exists() or not Menu.objects.exists():
        return
    padre = Menu.objects.filter(url="inventory:alertas").first()
    ultimo = Menu.objects.filter(parent=padre.parent if padre else None).order_by("-orden").first()
    Menu.objects.create(
        nombre="Pronóstico",
        url="inventory:pronostico",
        icono=padre.icono if padre else "chart-line",
        orden=(ultimo.orden + 1) if ultimo else 0,
        parent=padre.parent if padre else None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0005_menu_unidades"),
    ]

    operations = [
        migrations.RunPython(agregar, migrations.RunPython.noop),
    ]
