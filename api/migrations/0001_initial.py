import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TokenAPI",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, verbose_name="Nombre (para qué sistema es)")),
                ("inicio", models.CharField(editable=False, max_length=12, verbose_name="Inicio del token")),
                ("hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("ultimo_uso", models.DateTimeField(blank=True, null=True)),
                ("activo", models.BooleanField(default=True)),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="tokens_api",
                    to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={"verbose_name": "Token de API", "verbose_name_plural": "Tokens de API", "ordering": ["-creado"]},
        ),
    ]
