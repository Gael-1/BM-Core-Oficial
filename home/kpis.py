"""Indicadores del tablero de inicio."""
from datetime import timedelta

from django.db.models import F, FloatField, Q, Sum
from django.utils import timezone

from compra.models import EstatusChoices, OrdenDeCompra
from inventory.models import Inventario_Producto, Producto, Registro_Inventario

DIAS_ROTACION = 30
DIAS_GASTO = 90


def calcular_kpis(ahora=None):
    ahora = ahora or timezone.now()
    activos = Producto.objects.filter(activo=True)

    inventarios = Inventario_Producto.objects.filter(producto_id__activo=True)
    existencia_total = inventarios.aggregate(t=Sum("cantidad"))["t"] or 0.0
    valor_inventario = inventarios.aggregate(
        v=Sum(F("cantidad") * F("producto_id__precio"), output_field=FloatField())
    )["v"] or 0.0

    quiebres = activos.filter(Q(inventario__isnull=True) | Q(inventario__cantidad__lte=0)).count()

    salidas = Registro_Inventario.objects.filter(
        tipo_movimiento__in=("SALIDA", "BAJA"),
        creado__gte=ahora - timedelta(days=DIAS_ROTACION),
    ).aggregate(t=Sum("cantidad_nueva"))["t"] or 0.0
    rotacion = round(salidas / existencia_total, 2) if existencia_total > 0 else 0.0

    gasto = list(
        OrdenDeCompra.objects.filter(
            estatus=EstatusChoices.COMPLETADA,
            fecha_creado__gte=ahora - timedelta(days=DIAS_GASTO),
        )
        .values("proveedor__nombre")
        .annotate(total_gastado=Sum("total"))
        .order_by("-total_gastado")[:5]
    )
    maximo = max((g["total_gastado"] for g in gasto), default=0)
    for g in gasto:
        g["porcentaje"] = round(float(g["total_gastado"]) / float(maximo) * 100) if maximo else 0

    return {
        "valor_inventario": round(valor_inventario, 2),
        "unidades_en_existencia": round(existencia_total, 2),
        "productos_agotados": quiebres,
        "salidas_periodo": round(salidas, 2),
        "rotacion": rotacion,
        "gasto_proveedores": gasto,
        "dias_rotacion": DIAS_ROTACION,
        "dias_gasto": DIAS_GASTO,
    }
