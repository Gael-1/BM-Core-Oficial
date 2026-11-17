import csv

from django import forms
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from inventory.models import Producto, Registro_Inventario
from proveedores.models import Proveedor

# Incluye registros históricos y compras guardadas en minúsculas.
TIPOS = {
    "entrada": ("ENTRADA", "ALTA"),
    "salida": ("SALIDA", "BAJA"),
}
MAX_FILAS_EN_PANTALLA = 500


class FiltrosReporteForm(forms.Form):
    tipo_reporte = forms.ChoiceField(
        required=False,
        choices=[("", "Todos"), ("entrada", "Entradas"), ("salida", "Salidas")],
    )
    proveedor = forms.ModelChoiceField(queryset=Proveedor.objects.all(), required=False)
    producto = forms.ModelChoiceField(queryset=Producto.objects.all(), required=False)
    fecha_inicio = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    fecha_fin = forms.DateField(required=False, input_formats=["%Y-%m-%d"])

    def clean(self):
        datos = super().clean()
        inicio = datos.get("fecha_inicio")
        fin = datos.get("fecha_fin")
        if inicio and fin and inicio > fin:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha final.")
        return datos


def _filtro_tipo(tipos):
    filtro = Q()
    for tipo in tipos:
        filtro |= Q(tipo_movimiento__iexact=tipo)
    return filtro


def _total(movimientos, tipos):
    return movimientos.filter(_filtro_tipo(tipos)).aggregate(t=Sum("cantidad_nueva"))["t"] or 0


def _celda(valor):
    """Evita que Excel interprete texto de usuario como fórmula."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def _exportar_csv(movimientos):
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="reporte_movimientos.csv"'
    respuesta.write("\ufeff")  # BOM para que Excel respete los acentos
    escritor = csv.writer(respuesta)
    escritor.writerow(["Fecha", "Producto", "Tipo", "Cantidad", "Cantidad anterior",
                       "Motivo", "Proveedor", "Orden de compra", "Usuario", "Comentarios"])
    movimientos = movimientos.select_related(
        "inventario_producto_id__producto_id", "orden_compra__proveedor", "motivo", "creado_por"
    )
    for m in movimientos:
        inventario = m.inventario_producto_id
        orden = m.orden_compra
        escritor.writerow([
            timezone.localtime(m.creado).strftime("%Y-%m-%d %H:%M"),
            _celda(inventario.producto_id.nombre if inventario else "N/A"),
            _celda(m.tipo_movimiento),
            m.cantidad_nueva,
            "" if m.cantidad_anterior is None else m.cantidad_anterior,
            _celda(m.motivo),
            _celda(orden.proveedor.nombre if orden else ""),
            _celda(orden.numero_de_orden if orden else ""),
            _celda(m.creado_por.username),
            _celda(m.comentarios),
        ])
    return respuesta


def inicio_reportes(request):
    filtros = FiltrosReporteForm(request.GET)
    movimientos = Registro_Inventario.objects.select_related(
        "inventario_producto_id__producto_id", "orden_compra__proveedor", "motivo"
    ).order_by("-creado", "-pk")

    if filtros.is_valid():
        datos = filtros.cleaned_data
        if datos.get("tipo_reporte"):
            movimientos = movimientos.filter(_filtro_tipo(TIPOS[datos["tipo_reporte"]]))
        if datos.get("proveedor"):
            # Movimientos generados por la recepción de compras de ese proveedor.
            movimientos = movimientos.filter(orden_compra__proveedor=datos["proveedor"])
        if datos.get("producto"):
            movimientos = movimientos.filter(inventario_producto_id__producto_id=datos["producto"])
        if datos.get("fecha_inicio"):
            movimientos = movimientos.filter(creado__date__gte=datos["fecha_inicio"])
        if datos.get("fecha_fin"):
            movimientos = movimientos.filter(creado__date__lte=datos["fecha_fin"])
        if request.GET.get("exportar") == "csv":
            return _exportar_csv(movimientos)
    else:
        movimientos = movimientos.none()

    resumen = {
        "registros": movimientos.count(),
        "entradas": _total(movimientos, TIPOS["entrada"]),
        "salidas": _total(movimientos, TIPOS["salida"]),
        "limite": MAX_FILAS_EN_PANTALLA,
    }
    contexto = {
        "movimientos": movimientos,
        "errores_filtros": filtros.errors,
        "resumen": resumen,
        "proveedores": Proveedor.objects.order_by("nombre"),
        "productos": Producto.objects.order_by("nombre"),
    }
    return render(request, "inicio.html", contexto)
