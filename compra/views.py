import json
import uuid

from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from decimal import Decimal

from .forms import ConfiguracionComprasForm, OrdenDeCompraForm, formset
from .models import (
    ConfiguracionCompras,
    ProductosProveedor,
    OrdenDeCompra,
    ProductoEnOrden,
    EstatusChoices,
)
from inventory.models import (
    Producto,
    Registro_Inventario,
    Inventario_Producto,
    Negocio_Inventario,
    Registro_Negocio_Inventario,
)
from inventory import services
from negocio.models import Negocio
from django.shortcuts import redirect
from django.contrib import messages

# Create your views here.


def index(request):
    ordenes = OrdenDeCompra.objects.select_related("proveedor", "negocio").order_by("-fecha_creado")
    return render(request, "compra/index.html", {"ordenes": ordenes})


def add(request):
    form = OrdenDeCompraForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            orden = form.save(commit=False)
            orden.numero_de_orden = f"OC-{uuid.uuid4().hex[:16].upper()}"
            orden.usuario_creo = request.user
            orden.usuario_solicito = request.user
            orden.save()
            for linea in form.lineas:
                ProductoEnOrden.objects.create(orden=orden, usuario_creo=request.user, **linea)
            automatica = ConfiguracionCompras.obtener().aplica_a(Decimal(str(orden.total)))
            if automatica:
                orden.estatus = EstatusChoices.AUTORIZADA
                orden.autorizada_por_regla = True
                orden.usuario_modifico = request.user
                orden.save()
        if automatica:
            messages.success(request, "Orden creada y autorizada automáticamente por la regla de compras.")
        else:
            messages.success(request, "Orden creada correctamente. Está pendiente de autorización.")
        return redirect("compra:view", orden_id=orden.pk)
    productos_iniciales = []
    if request.method == "POST":
        try:
            datos = json.loads(request.POST.get("productos_json", "[]"))
            if isinstance(datos, list):
                productos_iniciales = [item for item in datos if isinstance(item, dict)]
        except (json.JSONDecodeError, TypeError):
            pass
    return render(request, "compra/add_edit.html", {
        "form": form, "productos_iniciales": productos_iniciales,
    })


def view(request, orden_id):
    orden = get_object_or_404(OrdenDeCompra, pk=orden_id)
    productos = ProductoEnOrden.objects.filter(orden=orden)
    return render(
        request, "compra/view.html", {"orden": orden, "productos_en_orden": productos}
    )


def findProductos(request):
    if request.method == "GET":
        proveedor_id = request.GET.get("proveedor")
        if not proveedor_id:
            return JsonResponse({"error": "Missing proveedor id"}, status=400)
        productosProveedor = ProductosProveedor.objects.filter(
            proveedor__id=proveedor_id, proveedor__activo=True, activo=True, producto__activo=True
        )
        response = [
            {
                "id": pp.producto.id,
                "nombre": pp.producto.nombre,
                "precio": str(pp.precio),
            }
            for pp in productosProveedor
        ]
        return JsonResponse(response, safe=False)
    return JsonResponse({"error": "Invalid request method"}, status=400)


def findNegocioRFC(request):
    if request.method == "POST":
        try:
            negocio_id = json.loads(request.body or b"{}").get("negocio_id")
        except (ValueError, AttributeError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        if not negocio_id:
            return JsonResponse({"error": "Missing negocio id"}, status=400)
        try:
            negocio = Negocio.objects.get(id=negocio_id)
        except (Negocio.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"error": "Negocio not found"}, status=404)
        response = {
            "rfc": negocio.rfc,
            "direccion": negocio.direccion,
        }
        return JsonResponse(response)
    return JsonResponse({"error": "Invalid request method"}, status=400)


@require_POST
def autorizar_oden(request, orden_id):
    return _cambiar_estado(request, orden_id, EstatusChoices.AUTORIZADA)


@require_POST
def rechazar_orden(request, orden_id):
    return _cambiar_estado(request, orden_id, EstatusChoices.RECHAZADA)


def _cambiar_estado(request, orden_id, estado):
    with transaction.atomic():
        orden = get_object_or_404(OrdenDeCompra.objects.select_for_update(), pk=orden_id)
        if not orden.activo or orden.estatus != EstatusChoices.PENDIENTE:
            messages.warning(request, "Solo puedes autorizar o rechazar una orden pendiente y activa.")
        elif (estado == EstatusChoices.AUTORIZADA and not request.user.is_superuser
              and orden.usuario_solicito_id == request.user.pk):
            messages.error(request, "No puedes autorizar una orden que tú mismo solicitaste.")
        elif not orden.productos.filter(activo=True).exists():
            messages.error(request, "La orden no contiene productos.")
        else:
            orden.estatus = estado
            orden.usuario_modifico = request.user
            if estado == EstatusChoices.AUTORIZADA:
                orden.usuario_autorizo = request.user
            orden.save()
            messages.success(request, "Orden autorizada." if estado == EstatusChoices.AUTORIZADA else "Orden rechazada.")
    return redirect("compra:view", orden_id=orden_id)


@require_POST
def completar_orden(request, orden_id):
    try:
        with transaction.atomic():
            # La comprobación del estado se hace DESPUÉS de bloquear la orden.
            orden = get_object_or_404(OrdenDeCompra.objects.select_for_update(), pk=orden_id)
            if not orden.activo or orden.estatus != EstatusChoices.AUTORIZADA:
                messages.warning(request, "Solo puedes recibir una orden autorizada y activa. Una orden completada no puede recibirse otra vez.")
                return redirect("compra:view", orden_id=orden_id)
            items = list(orden.productos.filter(activo=True).order_by("producto_id", "pk"))
            if not items:
                raise ValidationError("La orden no contiene productos activos.")
            for item in items:
                # Serializa también recepciones de distintas órdenes del mismo producto.
                producto = Producto.objects.select_for_update().get(pk=item.producto_id)
                if not producto.activo or item.cantidad <= 0:
                    raise ValidationError("La orden contiene un producto inactivo o una cantidad inválida.")
                inventario, _ = Inventario_Producto.objects.get_or_create(
                    producto_id=producto,
                    defaults={"cantidad": 0, "creado_por": request.user, "modificado_por": request.user},
                )
                services.asegurar_existencias(inventario)
                anterior = inventario.cantidad
                inventario.cantidad += item.cantidad
                inventario.modificado_por = request.user
                inventario.save()
                services.aplicar(inventario, inventario.almacen, item.cantidad)
                Registro_Inventario.objects.create(
                    inventario_producto_id=inventario, tipo_movimiento="ENTRADA",
                    cantidad_anterior=anterior, cantidad_nueva=item.cantidad,
                    almacen_destino=inventario.almacen, orden_compra=orden,
                    creado_por=request.user, comentarios=f"Recepción de {orden.numero_de_orden}",
                )
                negocio_inventario, _ = Negocio_Inventario.objects.get_or_create(
                    negocio=orden.negocio, producto=producto,
                    defaults={"cantidad": 0, "creado_por": request.user, "modificado_por": request.user},
                )
                anterior_negocio = negocio_inventario.cantidad
                negocio_inventario.cantidad += item.cantidad
                negocio_inventario.modificado_por = request.user
                negocio_inventario.save()
                Registro_Negocio_Inventario.objects.create(
                    negocio_inventario=negocio_inventario, cantidad_anterior=anterior_negocio,
                    cantidad_nueva=item.cantidad, creado_por=request.user,
                    comentarios=f"Recepción de {orden.numero_de_orden}",
                )
            orden.estatus = EstatusChoices.COMPLETADA
            orden.usuario_modifico = request.user
            orden.save()
            from api import webhooks
            webhooks.emitir("compra.recibida", {
                "numero_de_orden": orden.numero_de_orden, "proveedor": orden.proveedor.nombre, "total": str(orden.total),
            })
        messages.success(request, "Compra recibida. Las existencias se actualizaron correctamente.")
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    return redirect("compra:view", orden_id=orden_id)


def configuracion(request):
    """Reglas de automatización de compras (solo administrador)."""
    config = ConfiguracionCompras.obtener()
    form = ConfiguracionComprasForm(request.POST if request.method == "POST" else None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Reglas de compras guardadas.")
        return redirect("compra:configuracion")
    return render(request, "compra/configuracion.html", {"form": form})
