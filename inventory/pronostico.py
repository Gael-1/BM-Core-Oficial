"""Pronóstico estadístico básico de demanda (promedio de consumo, sin modelos de IA)."""
import math
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import Inventario_Producto, Registro_Inventario

VENTANA_DIAS = 30
HORIZONTE_DEFECTO = 30
HORIZONTE_MIN, HORIZONTE_MAX = 7, 90
TIPOS_SALIDA = ("SALIDA", "BAJA")


def normalizar_horizonte(valor):
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return HORIZONTE_DEFECTO
    return min(max(dias, HORIZONTE_MIN), HORIZONTE_MAX)


def _salidas_por_producto(desde, hasta):
    filas = (
        Registro_Inventario.objects.filter(
            tipo_movimiento__in=TIPOS_SALIDA, creado__gte=desde, creado__lt=hasta
        )
        .values("inventario_producto_id__producto_id")
        .annotate(total=Sum("cantidad_nueva"))
    )
    return {f["inventario_producto_id__producto_id"]: f["total"] or 0.0 for f in filas}


def calcular_pronostico(horizonte=HORIZONTE_DEFECTO, ahora=None):
    """Una fila por producto activo con existencia registrada.

    consumo_diario = salidas de los últimos 30 días / 30
    sugerido       = consumo_diario * horizonte + stock_min - existencia  (nunca negativo)
    tendencia      = cambio del consumo frente a los 30 días anteriores
    """
    horizonte = normalizar_horizonte(horizonte)
    ahora = ahora or timezone.now()
    inicio = ahora - timedelta(days=VENTANA_DIAS)
    actual = _salidas_por_producto(inicio, ahora + timedelta(seconds=1))
    previo = _salidas_por_producto(inicio - timedelta(days=VENTANA_DIAS), inicio)

    filas = []
    inventarios = Inventario_Producto.objects.filter(producto_id__activo=True).select_related(
        "producto_id", "producto_id__medida"
    )
    for inv in inventarios:
        producto = inv.producto_id
        salidas = actual.get(producto.pk, 0.0)
        consumo = salidas / VENTANA_DIAS
        necesario = consumo * horizonte + (producto.stock_min or 0) - inv.cantidad
        sugerido = max(0.0, necesario)
        enteras = producto.medida is not None and not producto.medida.permite_decimales
        sugerido = float(math.ceil(sugerido - 1e-9)) if enteras or producto.medida is None else round(sugerido, 2)
        anterior = previo.get(producto.pk, 0.0)
        if anterior > 0:
            tendencia = round((salidas - anterior) / anterior * 100)
        else:
            tendencia = None
        filas.append({
            "producto": producto,
            "existencia": inv.cantidad,
            "salidas_30d": round(salidas, 2),
            "consumo_diario": round(consumo, 2),
            "dias_cobertura": round(inv.cantidad / consumo, 1) if consumo > 0 else None,
            "sugerido": sugerido,
            "tendencia": tendencia,
            "tendencia_abs": abs(tendencia) if tendencia is not None else None,
        })
    # Primero lo que más urge comprar; después lo que se agota antes.
    filas.sort(key=lambda f: (-f["sugerido"], f["dias_cobertura"] if f["dias_cobertura"] is not None else 1e9))
    return filas
