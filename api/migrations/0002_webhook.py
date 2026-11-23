from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Webhook",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, verbose_name="Nombre (para qué sistema es)")),
                ("url", models.URLField(max_length=300, verbose_name="URL de destino")),
                ("eventos", models.CharField(help_text="Separados por coma.", max_length=200, verbose_name="Eventos")),
                ("secreto", models.CharField(editable=False, max_length=64)),
                ("activo", models.BooleanField(default=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("ultimo_envio", models.DateTimeField(blank=True, null=True)),
                ("ultimo_estado", models.CharField(blank=True, max_length=120)),
            ],
            options={"verbose_name": "Webhook", "verbose_name_plural": "Webhooks", "ordering": ["-creado"]},
        ),
    ]
