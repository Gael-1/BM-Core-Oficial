from django.db import migrations


def agregar(apps, schema_editor):
    Menu = apps.get_model("navigation", "Menu")
    if Menu.objects.filter(url="negocio:index").exists():
        return
    if not Menu.objects.exists():
        return  # sin menú en la base de datos se usa el menú fijo de layout.html
    ultimo = Menu.objects.filter(parent__isnull=True).order_by("-orden").first()
    Menu.objects.create(
        nombre="Negocios",
        url="negocio:index",
        icono="store",
        orden=(ultimo.orden + 1) if ultimo else 0,
        parent=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0003_menu_almacenes"),
    ]

    operations = [
        migrations.RunPython(agregar, migrations.RunPython.noop),
    ]
