"""Avisos salientes (webhooks): POST JSON firmado con HMAC-SHA256 en `X-BMCore-Signature`.

Se envían en segundo plano y solo después de confirmar la operación; un destino caído nunca
interrumpe una venta, una recepción ni un movimiento.
"""
import hashlib
import hmac
import json
import logging
import threading
import urllib.request

from django.db import transaction
from django.utils import timezone

from .models import Webhook

logger = logging.getLogger(__name__)
TIMEOUT = 5


def firmar(secreto, cuerpo):
    return hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()


def _enviar(hook, evento, cuerpo):
    solicitud = urllib.request.Request(
        hook.url, data=cuerpo, method="POST",
        headers={"Content-Type": "application/json", "X-BMCore-Event": evento,
                 "X-BMCore-Signature": "sha256=" + firmar(hook.secreto, cuerpo)},
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=TIMEOUT) as respuesta:  # noqa: S310 (http/https validado por URLField)
            estado = f"HTTP {respuesta.status}"
    except Exception as error:
        logger.warning("Webhook %s falló: %s", hook.pk, error)
        estado = f"Error: {error}"[:120]
    Webhook.objects.filter(pk=hook.pk).update(ultimo_envio=timezone.now(), ultimo_estado=estado)


def _despachar(hook, evento, cuerpo):
    threading.Thread(target=_enviar, args=(hook, evento, cuerpo), daemon=True).start()


def _entregar(evento, datos):
    cuerpo = json.dumps({"evento": evento, "fecha": timezone.now().isoformat(), "datos": datos},
                        ensure_ascii=False, default=str).encode("utf-8")
    for hook in Webhook.objects.filter(activo=True):
        if evento in hook.lista_eventos():
            _despachar(hook, evento, cuerpo)


def emitir(evento, datos):
    """Programa el aviso para después de confirmar la transacción actual."""
    try:
        transaction.on_commit(lambda: _entregar(evento, datos))
    except Exception:
        logger.exception("No se pudo programar el webhook %s.", evento)
