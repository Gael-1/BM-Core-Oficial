"""Avisos por correo cuando un producto llega a su stock mínimo.

Se envía un solo aviso por producto mientras siga bajo; al recuperarse por encima del mínimo
se rearma, y el siguiente descenso vuelve a avisar.
"""
import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from django.db.models import Q

from accounts.roles import ADMIN, ALMACEN

from .models import AlertaStock, Inventario_Producto

logger = logging.getLogger(__name__)


def destinatarios():
    """Correos de administradores, almacenistas y perfiles con permiso de inventario (activos)."""
    User = get_user_model()
    correos = (
        User.objects.filter(is_active=True)
        .filter(Q(groups__name__in=(ADMIN, ALMACEN)) | Q(groups__perfil_acceso__inventario=True))
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    return sorted(set(correos))


def esta_en_alerta(inventario):
    producto = inventario.producto_id
    return bool(producto.activo) and inventario.cantidad <= (producto.stock_min or 0)


def _enviar(inventarios):
    """Manda un correo con los productos indicados. Devuelve True si salió (o no había nada)."""
    if not inventarios:
        return True
    correos = destinatarios()
    if not correos:
        logger.warning("Hay productos con stock bajo pero ningún usuario con correo para avisarles.")
        return False
    lineas = [
        f"- {i.producto_id.nombre} ({i.producto_id.sku}): existencia {i.cantidad:g}, mínimo {i.producto_id.stock_min:g}"
        for i in inventarios
    ]
    asunto = (
        f"BM-Core: stock bajo en {inventarios[0].producto_id.nombre}"
        if len(inventarios) == 1
        else f"BM-Core: {len(inventarios)} productos con stock bajo"
    )
    cuerpo = "Los siguientes productos llegaron a su stock mínimo:\n\n" + "\n".join(lineas) + (
        "\n\nRevisa la sección Pronóstico para ver cuánto conviene comprar."
    )
    try:
        send_mail(asunto, cuerpo, None, correos, fail_silently=False)
    except Exception:  # un fallo de correo nunca debe romper un movimiento de inventario
        logger.exception("No se pudo enviar el aviso de stock bajo.")
        return False
    return True


def _marcar(inventarios):
    ahora = timezone.now()
    for inv in inventarios:
        AlertaStock.objects.update_or_create(
            producto=inv.producto_id, defaults={"notificado": ahora, "cantidad_al_notificar": inv.cantidad}
        )


def revisar(inventario_pk):
    """Avisa si el producto acaba de caer al mínimo; rearma la alerta si ya se recuperó."""
    inventario = Inventario_Producto.objects.select_related("producto_id").filter(pk=inventario_pk).first()
    if inventario is None:
        return False
    if not esta_en_alerta(inventario):
        AlertaStock.objects.filter(producto=inventario.producto_id).update(notificado=None)
        return False
    alerta = AlertaStock.objects.filter(producto=inventario.producto_id, notificado__isnull=False).exists()
    if alerta:
        return False
    if _enviar([inventario]):
        _marcar([inventario])
        return True
    return False


def enviar_pendientes(todos=False):
    """Un correo con todos los productos en alerta que aún no se avisaron (o todos con `todos`)."""
    en_alerta = [
        i for i in Inventario_Producto.objects.select_related("producto_id") if esta_en_alerta(i)
    ]
    avisados = set(
        AlertaStock.objects.filter(notificado__isnull=False).values_list("producto_id", flat=True)
    )
    pendientes = [i for i in en_alerta if todos or i.producto_id_id not in avisados]
    if pendientes and _enviar(pendientes):
        _marcar(pendientes)
        return len(pendientes)
    return 0
