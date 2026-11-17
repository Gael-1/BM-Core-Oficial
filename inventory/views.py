import uuid
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Q
from django.core.paginator import Paginator
from django.http import HttpResponse

from .models import Producto, Inventario_Producto, Registro_Inventario, Almacen
from .forms import MovimientoForm, addProductForm

logger = logging.getLogger(__name__)


def add(request, pk=None):
    if request.method == "POST":
        form = addProductForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    sku = form.cleaned_data["sku"]
                    codigo_barras = form.cleaned_data.get("codigo_barras")
                    nombre = form.cleaned_data["nombre"]
                    categoria_id = form.cleaned_data["categoria_id"]
                    descripcion = form.cleaned_data["descripcion"]
                    precio = form.cleaned_data["precio"]
                    cantidad = form.cleaned_data["cantidad"]
                    stock_min = form.cleaned_data["stock_min"]
                    imagen = form.files.get("imagen")
                    medida = form.cleaned_data["medida"]
                    almacen = form.cleaned_data.get("almacen")

                    sku = sku or f"SKU-{uuid.uuid4().hex[:8].upper()}"

                    producto = Producto.objects.create(
                        sku=sku,
                        codigo_barras=codigo_barras,
                        nombre=nombre,
                        categoria_id=categoria_id,
                        descripcion=descripcion,
                        precio=precio,
                        stock_min=stock_min,
                        creado_por=request.user,
                        modificado_por=request.user,
                        activo=True,
                        imagen=imagen,
                        medida=medida,
                    )
                    message = "Producto creado exitosamente."

                    cantidad = cantidad if form.cleaned_data.get("addCantidad") else 0
                    cantidad = cantidad or 0
                    inventario = Inventario_Producto.objects.create(
                        producto_id=producto, almacen=almacen, cantidad=cantidad,
                        creado_por=request.user, modificado_por=request.user,
                    )
                    if cantidad > 0:
                        Registro_Inventario.objects.create(
                            inventario_producto_id=inventario, almacen_destino=almacen,
                            cantidad_nueva=cantidad, cantidad_anterior=0,
                            tipo_movimiento="ENTRADA", creado_por=request.user,
                            comentarios="Alta inicial de producto",
                        )
                        message += " Inventario inicial añadido."

                    messages.success(request, message=message)
                    return redirect("inventory:productos")
            except Exception:
                logger.exception("No se pudo crear el producto")
                form.add_error(None, "No se pudo guardar el producto. Revisa los datos e inténtalo otra vez.")
    else:
        form = addProductForm()
    return render(request, "add.html", {"form": form})


def edit(request, pk):
    with transaction.atomic():
        # El producto funciona también como bloqueo cuando todavía no tiene inventario.
        producto = get_object_or_404(Producto.objects.select_for_update(), pk=pk)
        inventario = Inventario_Producto.objects.filter(producto_id=producto).first()
        actual = inventario.cantidad if inventario else 0
        initial = {"cantidad_actual": actual, "almacen": inventario.almacen_id if inventario else None}
        form = addProductForm(
            request.POST if request.method == "POST" else None,
            request.FILES if request.method == "POST" else None,
            instance=producto, initial=initial,
        )
        if request.method == "POST" and form.is_valid():
            nueva = form.cleaned_data.get("cantidad_nueva")
            almacen = form.cleaned_data.get("almacen")
            if nueva is not None and form.cleaned_data.get("cantidad_actual") != actual:
                form.add_error("cantidad_nueva", "El inventario cambió. Recarga la página antes de ajustar la cantidad.")
            if inventario and actual > 0 and (almacen.pk if almacen else None) != inventario.almacen_id:
                form.add_error("almacen", "No puedes cambiar de almacén con existencias. Se requiere un traspaso.")
            medida = form.cleaned_data.get("medida")
            if medida and not medida.permite_decimales and not float(actual).is_integer():
                form.add_error("medida", "La existencia actual contiene decimales; conserva una unidad compatible.")
            if not form.errors:
                producto = form.save(commit=False)
                producto.sku = producto.sku or f"SKU-{uuid.uuid4().hex[:8].upper()}"
                producto.modificado_por = request.user
                producto.save()
                if inventario is None:
                    inventario = Inventario_Producto.objects.create(
                        producto_id=producto, almacen=almacen, cantidad=0,
                        creado_por=request.user, modificado_por=request.user,
                    )
                inventario.almacen = almacen
                inventario.modificado_por = request.user
                if nueva is not None:
                    inventario.cantidad = nueva
                inventario.save()
                if nueva is not None and nueva != actual:
                    Registro_Inventario.objects.create(
                        inventario_producto_id=inventario,
                        almacen_destino=almacen if nueva > actual else None,
                        almacen_origen=almacen if nueva < actual else None,
                        cantidad_nueva=abs(nueva - actual), cantidad_anterior=actual,
                        tipo_movimiento="ENTRADA" if nueva > actual else "SALIDA",
                        creado_por=request.user, comentarios="Ajuste de existencia desde catálogo",
                    )
                messages.success(request, "Producto actualizado correctamente.")
                return redirect("inventory:productos")
    return render(request, "add.html", {
        "form": form, "edit": True, "producto": producto, "inventario": inventario,
    })


def productos(request):
    productos_qs = Producto.objects.select_related("inventario", "medida").filter(activo=True)
    return render(request, "productos.html", {"productos": productos_qs})


# --- NUEVAS VISTAS FASE 1 (HTMX & BUSQUEDA) ---

def buscar_producto_codigo(request):
    """Búsqueda optimizada por Lector de Código de Barras o SKU vía HTMX."""
    query = request.GET.get('q', '').strip()
    

    producto = Producto.objects.filter(
        activo=True
    ).filter(
        codigo_barras=query
    ).first() or Producto.objects.filter(sku=query, activo=True).first()

    context = {'producto': producto, 'query': query}

    if request.headers.get('HX-Request'):
        return render(request, 'inventory/partials/producto_card.html', context)
    
    return render(request, 'inventory/buscar_codigo.html', context)


def alertas_reabastecimiento(request):
    """Consulta de productos en o por debajo de su punto de reorden (stock_min)."""
    productos_bajo_stock = Producto.objects.filter(
        activo=True,
    ).filter(Q(inventario__cantidad__lte=F('stock_min')) | Q(inventario__isnull=True)).select_related('categoria_id', 'inventario', 'medida')

    context = {
        'productos': productos_bajo_stock,
        'total_alertas': productos_bajo_stock.count()
    }

    if request.headers.get('HX-Request'):
        return render(request, 'inventory/partials/tabla_alertas.html', context)

    return render(request, 'inventory/alertas.html', context)


def inventario_por_almacen(request):
    """Filtra la lista de existencias según el almacén seleccionado."""
    almacen_id = request.GET.get('almacen_id')
    almacenes = Almacen.objects.all()
    
    inventario_qs = Inventario_Producto.objects.select_related(
        'producto_id', 'almacen', 'negocio'
    ).all()

    if almacen_id:
        if not almacen_id.isdigit():
            return HttpResponse("Selecciona un almacén válido.", status=400)
        inventario_qs = inventario_qs.filter(almacen_id=almacen_id)

    context = {
        'inventario': inventario_qs,
        'almacenes': almacenes,
        'almacen_seleccionado': almacen_id
    }

    if request.headers.get('HX-Request'):
        return render(request, 'inventory/partials/tabla_inventario.html', context)

    return render(request, 'inventory/inventario_almacen.html', context)


# --- ENTRADAS, SALIDAS E HISTORIAL ---

TIPOS_HISTORIAL = {
    # Incluye registros históricos guardados como ALTA / BAJA.
    "ENTRADA": ("ENTRADA", "ALTA"),
    "SALIDA": ("SALIDA", "BAJA"),
    "TRASPASO": ("TRASPASO",),
}


def registrar_movimiento(request):
    """Registra una entrada o salida manual y actualiza la existencia."""
    producto_inicial = request.GET.get("producto", "")
    form = MovimientoForm(
        request.POST if request.method == "POST" else None,
        initial={"producto": producto_inicial} if producto_inicial.isdigit() else None,
    )
    if request.method == "POST" and form.is_valid():
        tipo = form.cleaned_data["tipo_movimiento"]
        cantidad = form.cleaned_data["cantidad"]
        with transaction.atomic():
            # El bloqueo del producto serializa movimientos simultáneos del mismo artículo.
            producto = Producto.objects.select_for_update().get(pk=form.cleaned_data["producto"].pk)
            inventario = Inventario_Producto.objects.filter(producto_id=producto).first()
            anterior = inventario.cantidad if inventario else 0.0
            if tipo == "SALIDA" and cantidad - anterior > 1e-9:
                form.add_error("cantidad", f"Existencia insuficiente: hay {anterior:g} disponibles.")
            else:
                if inventario is None:
                    inventario = Inventario_Producto.objects.create(
                        producto_id=producto, cantidad=0,
                        creado_por=request.user, modificado_por=request.user,
                    )
                nueva = anterior + cantidad if tipo == "ENTRADA" else anterior - cantidad
                inventario.cantidad = round(nueva, 4)
                inventario.modificado_por = request.user
                inventario.save()
                Registro_Inventario.objects.create(
                    inventario_producto_id=inventario,
                    tipo_movimiento=tipo,
                    cantidad_anterior=anterior,
                    cantidad_nueva=cantidad,
                    almacen_destino=inventario.almacen if tipo == "ENTRADA" else None,
                    almacen_origen=inventario.almacen if tipo == "SALIDA" else None,
                    motivo=form.cleaned_data["motivo"],
                    comentarios=form.cleaned_data["comentarios"] or None,
                    creado_por=request.user,
                )
                messages.success(request, "Movimiento registrado correctamente.")
                return redirect("inventory:historial")
    return render(request, "inventory/movimiento.html", {"form": form})


def historial_movimientos(request):
    """Historial paginado de movimientos, filtrable por tipo y producto."""
    movimientos = Registro_Inventario.objects.select_related(
        "inventario_producto_id__producto_id", "creado_por", "motivo", "orden_compra"
    ).order_by("-creado", "-pk")

    tipo = request.GET.get("tipo", "")
    producto_id = request.GET.get("producto", "")
    if tipo in TIPOS_HISTORIAL:
        filtro = Q()
        for valor in TIPOS_HISTORIAL[tipo]:
            filtro |= Q(tipo_movimiento__iexact=valor)
        movimientos = movimientos.filter(filtro)
    if producto_id.isdigit():
        movimientos = movimientos.filter(inventario_producto_id__producto_id=int(producto_id))

    parametros = request.GET.copy()
    parametros.pop("page", None)
    return render(request, "inventory/historial.html", {
        "page_obj": Paginator(movimientos, 25).get_page(request.GET.get("page")),
        "productos": Producto.objects.filter(activo=True).order_by("nombre"),
        "tipo": tipo,
        "producto_id": producto_id,
        "querystring": parametros.urlencode(),
    })
