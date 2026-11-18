"""Pronóstico estadístico de demanda.

Con historial suficiente se usa suavizado exponencial doble (método de Holt) sobre el consumo
semanal, que capta nivel y tendencia. Con poco historial se usa el promedio simple de 30 días.
No es aprendizaje automático: es estadística clásica, explicable y sin dependencias externas.
"""
import math
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import Inventario_Producto, Registro_Inventario

VENTANA_DIAS = 30
HORIZONTE_DEFECTO = 30
HORIZONTE_MIN, HORIZONTE_MAX = 7, 90
TIPOS_SALIDA = ("SALIDA", "BAJA")
SEMANAS_HISTORIAL = 12
MIN_SEMANAS_CON_DATOS = 3
ALFA, BETA = 0.4, 0.2


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


def serie_semanal(fechas_y_cantidades, ahora, semanas=SEMANAS_HISTORIAL):
    """Consumo por semana, de la más antigua a la más reciente (la última termina en `ahora`)."""
    serie = [0.0] * semanas
    for fecha, cantidad in fechas_y_cantidades:
        antiguedad = int((ahora - fecha).total_seconds() // (7 * 86400))
        if 0 <= antiguedad < semanas:
            serie[semanas - 1 - antiguedad] += cantidad or 0.0
    return serie


def holt(serie, alfa=ALFA, beta=BETA):
    """Suavizado exponencial doble. Devuelve (nivel, tendencia, error_absoluto_medio_un_paso)."""
    if len(serie) < 2:
        raise ValueError("Se necesitan al menos dos periodos.")
    nivel, tendencia = serie[0], serie[1] - serie[0]
    errores = []
    for valor in serie[1:]:
        errores.append(abs(valor - (nivel + tendencia)))
        anterior = nivel
        nivel = alfa * valor + (1 - alfa) * (nivel + tendencia)
        tendencia = beta * (nivel - anterior) + (1 - beta) * tendencia
    return nivel, tendencia, sum(errores) / len(errores)


def pronosticar_semanas(serie, semanas_adelante, alfa=ALFA, beta=BETA):
    """Consumo esperado de cada una de las próximas semanas (nunca negativo)."""
    nivel, tendencia, _ = holt(serie, alfa, beta)
    return [max(0.0, nivel + k * tendencia) for k in range(1, semanas_adelante + 1)]


def demanda_en_dias(serie, dias, alfa=ALFA, beta=BETA):
    """Demanda total esperada en los próximos `dias` (la última semana se prorratea)."""
    semanas = math.ceil(dias / 7)
    total = 0.0
    for i, esperado in enumerate(pronosticar_semanas(serie, semanas, alfa, beta)):
        total += esperado * (min(7, dias - 7 * i) / 7)
    return total


def calcular_pronostico(horizonte=HORIZONTE_DEFECTO, ahora=None):
    """Una fila por producto activo con existencia registrada.

    consumo_diario = salidas de los últimos 30 días / 30
    demanda        = Holt sobre las últimas 12 semanas (o consumo_diario * horizonte si hay pocos datos)
    sugerido       = demanda + stock_min - existencia  (nunca negativo)
    tendencia      = cambio del consumo frente a los 30 días anteriores
    """
    horizonte = normalizar_horizonte(horizonte)
    ahora = ahora or timezone.now()
    inicio = ahora - timedelta(days=VENTANA_DIAS)
    actual = _salidas_por_producto(inicio, ahora + timedelta(seconds=1))
    previo = _salidas_por_producto(inicio - timedelta(days=VENTANA_DIAS), inicio)

    historial = {}
    desde = ahora - timedelta(days=7 * SEMANAS_HISTORIAL)
    for producto_id, fecha, cantidad in Registro_Inventario.objects.filter(
        tipo_movimiento__in=TIPOS_SALIDA, creado__gte=desde
    ).values_list("inventario_producto_id__producto_id", "creado", "cantidad_nueva"):
        historial.setdefault(producto_id, []).append((fecha, cantidad))

    filas = []
    inventarios = Inventario_Producto.objects.filter(producto_id__activo=True).select_related(
        "producto_id", "producto_id__medida"
    )
    for inv in inventarios:
        producto = inv.producto_id
        salidas = actual.get(producto.pk, 0.0)
        consumo = salidas / VENTANA_DIAS
        demanda_simple = consumo * horizonte
        serie = serie_semanal(historial.get(producto.pk, []), ahora)
        suficiente = sum(1 for v in serie if v > 0) >= MIN_SEMANAS_CON_DATOS
        if suficiente:
            demanda = demanda_en_dias(serie, horizonte)
            media = sum(serie) / len(serie)
            error_pct = round(holt(serie)[2] / media * 100) if media > 0 else None
        else:
            demanda, error_pct = demanda_simple, None
        necesario = demanda + (producto.stock_min or 0) - inv.cantidad
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
            "metodo": "suavizado" if suficiente else "promedio",
            "demanda_estimada": round(demanda, 2),
            "demanda_simple": round(demanda_simple, 2),
            "error_pct": error_pct,
            "tendencia": tendencia,
            "tendencia_abs": abs(tendencia) if tendencia is not None else None,
        })
    # Primero lo que más urge comprar; después lo que se agota antes.
    filas.sort(key=lambda f: (-f["sugerido"], f["dias_cobertura"] if f["dias_cobertura"] is not None else 1e9))
    return filas
