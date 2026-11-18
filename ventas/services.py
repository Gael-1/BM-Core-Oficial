"""Registro y cancelación de ventas. Cada venta descuenta existencias del almacén elegido."""
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from inventory import services as inventario
from inventory.models import motivo_movimiento

from .models import EstatusVenta, LineaVenta, OrigenVenta, Venta

MAX_LINEAS = 100
CENTAVOS = Decimal("0.01")


class VentaInvalida(ValueError):
    """La venta no se puede registrar o cancelar con los datos recibidos."""


def _motivo(nombre, descripcion):
    return motivo_movimiento.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})[0]


def _precio(valor, producto):
    if valor is None or valor == "":
        return Decimal(str(producto.precio)).quantize(CENTAVOS, ROUND_HALF_UP)
    try:
        precio = Decimal(str(valor))
    except InvalidOperation:
        raise VentaInvalida(f"El precio de «{producto.nombre}» no es un número válido.")
    if not precio.is_finite() or precio < 0:
        raise VentaInvalida(f"El precio de «{producto.nombre}» debe ser cero o mayor.")
    return precio.quantize(CENTAVOS, ROUND_HALF_UP)


def crear_venta(usuario, almacen, lineas, cliente_nombre="", referencia=None, comentarios="", origen=OrigenVenta.WEB):
    """Registra la venta y descuenta cada línea del almacén.

    `lineas`: lista de dicts {producto, cantidad, precio_unitario (opcional)}.
    Devuelve (venta, creada). Si `referencia` ya existe devuelve la venta anterior con creada=False.
    Si algo falla (existencia insuficiente, unidad, producto inactivo) no se guarda nada.
    """
    referencia = (referencia or "").strip() or None
    if referencia:
        previa = Venta.objects.filter(referencia_externa=referencia).first()
        if previa:
            return previa, False
    if almacen is None:
        raise VentaInvalida("Elige el almacén del que sale la mercancía.")
    if not lineas:
        raise VentaInvalida("Agrega al menos un producto a la venta.")
    if len(lineas) > MAX_LINEAS:
        raise VentaInvalida(f"Una venta admite hasta {MAX_LINEAS} productos.")

    try:
        return _registrar(usuario, almacen, lineas, cliente_nombre, referencia, comentarios, origen), True
    except IntegrityError:
        # Otra petición con la misma referencia ganó la carrera: se devuelve esa venta.
        previa = Venta.objects.filter(referencia_externa=referencia).first() if referencia else None
        if previa:
            return previa, False
        raise


def _registrar(usuario, almacen, lineas, cliente_nombre, referencia, comentarios, origen):
    with transaction.atomic():
        venta = Venta.objects.create(
            folio=f"VT-{uuid.uuid4().hex[:12].upper()}", negocio=almacen.negocio, almacen=almacen,
            cliente_nombre=(cliente_nombre or "").strip()[:150], referencia_externa=referencia,
            origen=origen, comentarios=(comentarios or "")[:255], usuario=usuario,
        )
        motivo = _motivo("Venta", "Salida por venta o entrega a cliente")
        total = Decimal("0")
        for linea in lineas:
            producto, cantidad = linea["producto"], linea["cantidad"]
            precio = _precio(linea.get("precio_unitario"), producto)
            try:
                inventario.registrar_movimiento(
                    producto, "SALIDA", cantidad, usuario, almacen=almacen, motivo=motivo,
                    comentarios=f"Venta {venta.folio}",
                )
            except inventario.MovimientoInvalido as error:
                raise VentaInvalida(f"{producto.nombre}: {error}")
            except inventario.ExistenciaInsuficiente as error:
                raise VentaInvalida(f"{producto.nombre}: {error}")
            subtotal = (Decimal(str(cantidad)) * precio).quantize(CENTAVOS, ROUND_HALF_UP)
            LineaVenta.objects.create(
                venta=venta, producto=producto, cantidad=float(cantidad), precio_unitario=precio, subtotal=subtotal
            )
            total += subtotal
        venta.total = total
        venta.save(update_fields=["total"])
    return venta


def cancelar_venta(venta, usuario):
    """Devuelve al almacén lo vendido y marca la venta como cancelada (solo una vez)."""
    with transaction.atomic():
        venta = Venta.objects.select_for_update().get(pk=venta.pk)
        if venta.estatus != EstatusVenta.COMPLETADA:
            raise VentaInvalida("Esta venta ya estaba cancelada.")
        motivo = _motivo("Devolución", "Devolución a proveedor o de un cliente")
        for linea in venta.lineas.select_related("producto"):
            inventario.registrar_movimiento(
                linea.producto, "ENTRADA", linea.cantidad, usuario, almacen=venta.almacen, motivo=motivo,
                comentarios=f"Cancelación de {venta.folio}", permitir_inactivo=True,
            )
        venta.estatus = EstatusVenta.CANCELADA
        venta.cancelada_por = usuario
        venta.cancelada_en = timezone.now()
        venta.save(update_fields=["estatus", "cancelada_por", "cancelada_en"])
    return venta
