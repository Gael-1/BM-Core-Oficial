from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Inventario_Producto


@receiver(post_save, sender=Inventario_Producto)
def revisar_alerta_de_stock(sender, instance, **kwargs):
    from . import alertas

    # Hasta que la operación se confirme, para no avisar de movimientos que se reviertan.
    transaction.on_commit(lambda: alertas.revisar(instance.pk))
