from django.db import migrations


def agregar(apps, schema_editor):
    Menu = apps.get_model("navigation", "Menu")
    if Menu.objects.filter(url="ventas:index").exists() or not Menu.objects.exists():
        return
    padre = Menu.objects.filter(url="compra:index").first()
    ultimo = Menu.objects.filter(parent=padre.parent if padre else None).order_by("-orden").first()
    Menu.objects.create(
        nombre="Ventas",
        url="ventas:index",
        icono=padre.icono if padre else "cash-register",
        orden=(ultimo.orden + 1) if ultimo else 0,
        parent=padre.parent if padre else None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0006_menu_pronostico"),
    ]

    operations = [
        migrations.RunPython(agregar, migrations.RunPython.noop),
    ]
