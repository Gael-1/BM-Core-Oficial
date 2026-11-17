"""Existencias por almacén.

Reglas:
* `Inventario_Producto.cantidad` es el total del producto.
* `Existencia_Almacen` desglosa ese total por almacén.
* Lo que no está desglosado ("sin asignar") se atribuye al almacén predeterminado del
  inventario (`Inventario_Producto.almacen`) en cuanto se llama a `asegurar_existencias`.
  Así los datos anteriores a esta función, o creados desde el admin, se corrigen solos.

Todas las funciones deben llamarse dentro de `transaction.atomic()` y con el producto
bloqueado (`select_for_update`), como ya hacen las vistas.
"""
from django.db.models import Sum

from .models import Existencia_Almacen

EPS = 1e-9


class ExistenciaInsuficiente(Exception):
    """El almacén no tiene suficiente cantidad para el movimiento."""


def _fila(inventario, almacen_id, bloquear=False):
    consulta = Existencia_Almacen.objects.filter(inventario=inventario, almacen_id=almacen_id)
    if bloquear:
        consulta = consulta.select_for_update()
    return consulta.first()


def asignado(inventario):
    total = Existencia_Almacen.objects.filter(inventario=inventario).aggregate(t=Sum("cantidad"))["t"]
    return total or 0.0


def sin_asignar(inventario):
    return max(0.0, round(inventario.cantidad - asignado(inventario), 4))


def existencia_en(inventario, almacen):
    """Cantidad disponible en `almacen` (None = sin asignar)."""
    if almacen is None:
        return sin_asignar(inventario)
    fila = _fila(inventario, almacen.pk)
    return fila.cantidad if fila else 0.0


def puede_retirar(inventario, almacen, cantidad):
    return existencia_en(inventario, almacen) + EPS >= cantidad


def mover(inventario, almacen, delta):
    """Suma `delta` (positivo o negativo) a la fila del almacén."""
    fila = _fila(inventario, almacen.pk, bloquear=True)
    if fila is None:
        fila = Existencia_Almacen(inventario=inventario, almacen=almacen, cantidad=0)
    nueva = round(fila.cantidad + delta, 4)
    if nueva < -EPS:
        raise ExistenciaInsuficiente(f"{almacen.nombre}: hay {fila.cantidad:g}")
    fila.cantidad = max(nueva, 0.0)
    fila.save()


def aplicar(inventario, almacen, delta):
    """Refleja en el desglose un cambio del total. Sin almacén, el cambio queda sin asignar."""
    if almacen is None or delta == 0:
        return
    mover(inventario, almacen, delta)


def asegurar_existencias(inventario):
    """Atribuye al almacén predeterminado lo que aún no está desglosado."""
    if inventario is None or inventario.almacen_id is None:
        return
    pendiente = sin_asignar(inventario)
    if pendiente > EPS:
        mover(inventario, inventario.almacen, pendiente)


def desglose(inventario):
    """Lista de (almacen o None, cantidad) con cantidad > 0, incluyendo lo sin asignar."""
    filas = [
        (fila.almacen, fila.cantidad)
        for fila in Existencia_Almacen.objects.filter(inventario=inventario, cantidad__gt=0).select_related("almacen")
    ]
    resto = sin_asignar(inventario)
    if resto > EPS:
        filas.append((inventario.almacen, resto))
    return filas


def inventario_de_negocio(negocio):
    """Existencias reales de un negocio: suma lo que hay en sus almacenes.

    Devuelve una lista de dicts {producto, cantidad, almacenes: [(almacen, cantidad)]},
    ordenada por nombre de producto. Incluye traspasos, salidas y ajustes, a diferencia del
    historial de compras de Negocio_Inventario.
    """
    from .models import Inventario_Producto

    por_producto = {}
    inventarios = Inventario_Producto.objects.select_related("producto_id", "almacen").prefetch_related(
        "existencias__almacen"
    )
    for inventario in inventarios:
        filas = [
            (fila.almacen, fila.cantidad)
            for fila in inventario.existencias.all()
            if fila.cantidad > 0
        ]
        resto = sin_asignar(inventario)
        if resto > EPS:
            filas.append((inventario.almacen, resto))
        filas = [(a, c) for a, c in filas if a is not None and a.negocio_id == negocio.pk]
        if not filas:
            continue
        por_producto[inventario.producto_id_id] = {
            "producto": inventario.producto_id,
            "cantidad": round(sum(c for _, c in filas), 4),
            "almacenes": filas,
        }
    return sorted(por_producto.values(), key=lambda f: f["producto"].nombre.lower())
