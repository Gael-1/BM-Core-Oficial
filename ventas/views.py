from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventory.services import ExistenciaInsuficiente

from . import facturacion, services
from .forms import ClienteForm, LineaVentaFormSet, VentaForm
from .models import Cliente, EstatusVenta, Venta


def index(request):
    ventas = Venta.objects.select_related("almacen", "usuario")
    estatus = request.GET.get("estatus", "")
    if estatus in EstatusVenta.values:
        ventas = ventas.filter(estatus=estatus)
    pagina = Paginator(ventas, 25).get_page(request.GET.get("pagina"))
    return render(request, "ventas/index.html", {"page_obj": pagina, "estatus": estatus})


def nueva(request):
    form = VentaForm(request.POST if request.method == "POST" else None)
    formset = LineaVentaFormSet(request.POST if request.method == "POST" else None, prefix="lineas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        lineas = [
            {"producto": f.cleaned_data["producto"], "cantidad": f.cleaned_data["cantidad"],
             "precio_unitario": f.cleaned_data.get("precio_unitario")}
            for f in formset if f.cleaned_data.get("producto")
        ]
        try:
            venta, _ = services.crear_venta(
                request.user, form.cleaned_data["almacen"], lineas,
                cliente_nombre=form.cleaned_data["cliente_nombre"] or (
                    form.cleaned_data["cliente"].nombre if form.cleaned_data["cliente"] else ""),
                comentarios=form.cleaned_data["comentarios"], cliente=form.cleaned_data["cliente"],
            )
        except (services.VentaInvalida, ExistenciaInsuficiente) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Venta {venta.folio} registrada. Las existencias se descontaron.")
            return redirect("ventas:detalle", pk=venta.pk)
    return render(request, "ventas/nueva.html", {"form": form, "formset": formset})


def detalle(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("almacen", "usuario", "cancelada_por"), pk=pk)
    return render(request, "ventas/detalle.html", {
        "venta": venta, "lineas": venta.lineas.select_related("producto"),
        "prefactura": getattr(venta, "prefactura", None),
        "clientes": Cliente.objects.filter(activo=True),
        "timbrado_disponible": facturacion.timbrado_disponible(),
    })


@require_POST
def cancelar(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    try:
        services.cancelar_venta(venta, request.user)
    except (services.VentaInvalida, ExistenciaInsuficiente) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Venta cancelada. La mercancía regresó al almacén.")
    return redirect("ventas:detalle", pk=pk)


def clientes(request):
    return render(request, "ventas/clientes.html", {"clientes": Cliente.objects.select_related("regimen_fiscal")})


def cliente_add_edit(request, pk=None):
    cliente = get_object_or_404(Cliente, pk=pk) if pk else None
    form = ClienteForm(request.POST if request.method == "POST" else None, instance=cliente)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cliente guardado correctamente.")
        return redirect("ventas:clientes")
    return render(request, "ventas/cliente_form.html", {"form": form, "cliente": cliente})


@require_POST
def generar_prefactura(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    cliente = Cliente.objects.filter(pk=request.POST.get("cliente"), activo=True).first() \
        if request.POST.get("cliente", "").isdigit() else None
    try:
        facturacion.generar_prefactura(venta, cliente, request.user)
    except facturacion.PrefacturaInvalida as error:
        messages.error(request, str(error))
        return redirect("ventas:detalle", pk=pk)
    messages.success(request, "Prefactura generada.")
    return redirect("ventas:prefactura", pk=pk)


def prefactura(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("prefactura"), pk=pk)
    if not hasattr(venta, "prefactura"):
        messages.warning(request, "Esta venta todavía no tiene prefactura.")
        return redirect("ventas:detalle", pk=pk)
    return render(request, "ventas/prefactura.html", {
        "venta": venta, "p": venta.prefactura, "d": venta.prefactura.datos, "aviso": facturacion.AVISO,
    })


def prefactura_xml(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("prefactura"), pk=pk)
    if not hasattr(venta, "prefactura"):
        messages.warning(request, "Esta venta todavía no tiene prefactura.")
        return redirect("ventas:detalle", pk=pk)
    respuesta = HttpResponse(facturacion.construir_xml(venta.prefactura), content_type="application/xml; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="{venta.prefactura.numero}.xml"'
    return respuesta
