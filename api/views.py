import json

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from inventory import services
from inventory.models import Almacen, Producto, Registro_Inventario, motivo_movimiento

LIMITE_MAXIMO = 100


def _producto(p, detalle=False):
    inventario = getattr(p, "inventario", None)
    datos = {
        "id": p.pk,
        "sku": p.sku,
        "codigo_barras": p.codigo_barras,
        "nombre": p.nombre,
        "categoria": p.categoria_id.nombre if p.categoria_id_id else None,
        "medida": p.medida.nombre if p.medida_id else None,
        "precio": str(p.precio),
        "stock_min": p.stock_min,
        "activo": p.activo,
        "existencia": inventario.cantidad if inventario else 0,
    }
    if detalle:
        datos["almacenes"] = (
            [{"almacen_id": a.pk if a else None, "almacen": a.nombre if a else "Sin asignar", "cantidad": c}
             for a, c in services.desglose(inventario)]
            if inventario else []
        )
    return datos


def _entero(valor, defecto, minimo=1, maximo=None):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return defecto
    numero = max(numero, minimo)
    return min(numero, maximo) if maximo else numero


@require_http_methods(["GET"])
def productos(request):
    consulta = Producto.objects.select_related("categoria_id", "medida", "inventario").order_by("nombre", "pk")
    activo = request.GET.get("activo")
    if activo in ("true", "false"):
        consulta = consulta.filter(activo=(activo == "true"))
    q = request.GET.get("q", "").strip()
    if q:
        consulta = consulta.filter(Q(nombre__icontains=q) | Q(sku__iexact=q) | Q(codigo_barras=q))
    pagina = Paginator(consulta, _entero(request.GET.get("limite"), 25, 1, LIMITE_MAXIMO)).get_page(
        _entero(request.GET.get("pagina"), 1)
    )
    return JsonResponse({
        "total": pagina.paginator.count,
        "pagina": pagina.number,
        "paginas": pagina.paginator.num_pages,
        "resultados": [_producto(p) for p in pagina],
    })


@require_http_methods(["GET"])
def producto_detalle(request, pk):
    p = Producto.objects.select_related("categoria_id", "medida", "inventario").filter(pk=pk).first()
    if p is None:
        return JsonResponse({"error": "Producto no encontrado."}, status=404)
    return JsonResponse(_producto(p, detalle=True))


@require_http_methods(["GET"])
def almacenes(request):
    return JsonResponse({"resultados": [
        {"id": a.pk, "nombre": a.nombre, "negocio": a.negocio.nombre if a.negocio else None,
         "es_principal": a.es_principal}
        for a in Almacen.objects.select_related("negocio").order_by("nombre")
    ]})


def _movimiento(m):
    return {
        "id": m.pk,
        "producto_id": m.inventario_producto_id.producto_id_id,
        "tipo": m.tipo_movimiento,
        "cantidad": m.cantidad_nueva,
        "cantidad_anterior": m.cantidad_anterior,
        "almacen_origen": m.almacen_origen.nombre if m.almacen_origen else None,
        "almacen_destino": m.almacen_destino.nombre if m.almacen_destino else None,
        "motivo": m.motivo.nombre if m.motivo else None,
        "comentarios": m.comentarios,
        "fecha": m.creado.isoformat(),
    }


def _crear_movimiento(request):
    try:
        datos = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "El cuerpo debe ser JSON válido."}, status=400)
    if not isinstance(datos, dict):
        return JsonResponse({"error": "El cuerpo debe ser un objeto JSON."}, status=400)

    if datos.get("producto") is not None:
        producto = Producto.objects.filter(pk=datos["producto"]).first() if isinstance(datos["producto"], int) else None
    else:
        sku = str(datos.get("sku", "")).strip()
        producto = Producto.objects.filter(sku=sku).first() if sku else None
    if producto is None:
        return JsonResponse({"error": "Indica un producto existente con «producto» (id) o «sku»."}, status=404)

    almacen = None
    if datos.get("almacen") is not None:
        almacen = Almacen.objects.filter(pk=datos["almacen"]).first() if isinstance(datos["almacen"], int) else None
        if almacen is None:
            return JsonResponse({"error": "El almacén indicado no existe."}, status=400)
    motivo = None
    if datos.get("motivo") is not None:
        motivo = motivo_movimiento.objects.filter(pk=datos["motivo"], activo=True).first() \
            if isinstance(datos["motivo"], int) else None
        if motivo is None:
            return JsonResponse({"error": "El motivo indicado no existe."}, status=400)
    comentarios = str(datos.get("comentarios") or "")[:255]

    try:
        with transaction.atomic():
            inventario, registro = services.registrar_movimiento(
                producto, str(datos.get("tipo") or "").upper(), datos.get("cantidad"), request.user,
                almacen=almacen, motivo=motivo, comentarios=comentarios or "API",
            )
    except (services.MovimientoInvalido, services.ExistenciaInsuficiente) as error:
        return JsonResponse({"error": str(error)}, status=400 if isinstance(error, services.MovimientoInvalido) else 409)
    return JsonResponse({"movimiento": _movimiento(registro), "existencia": inventario.cantidad}, status=201)


@require_http_methods(["GET", "POST"])
def movimientos(request):
    if request.method == "POST":
        return _crear_movimiento(request)
    consulta = Registro_Inventario.objects.select_related(
        "inventario_producto_id", "almacen_origen", "almacen_destino", "motivo"
    ).order_by("-creado", "-pk")
    if request.GET.get("producto", "").isdigit():
        consulta = consulta.filter(inventario_producto_id__producto_id=int(request.GET["producto"]))
    if request.GET.get("tipo", "").upper() in ("ENTRADA", "SALIDA", "TRASPASO"):
        consulta = consulta.filter(tipo_movimiento=request.GET["tipo"].upper())
    limite = _entero(request.GET.get("limite"), 25, 1, LIMITE_MAXIMO)
    return JsonResponse({"resultados": [_movimiento(m) for m in consulta[:limite]]})
