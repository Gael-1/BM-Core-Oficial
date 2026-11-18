from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventory.services import ExistenciaInsuficiente

from . import services
from .forms import LineaVentaFormSet, VentaForm
from .models import EstatusVenta, Venta


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
                cliente_nombre=form.cleaned_data["cliente_nombre"], comentarios=form.cleaned_data["comentarios"],
            )
        except (services.VentaInvalida, ExistenciaInsuficiente) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Venta {venta.folio} registrada. Las existencias se descontaron.")
            return redirect("ventas:detalle", pk=venta.pk)
    return render(request, "ventas/nueva.html", {"form": form, "formset": formset})


def detalle(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("almacen", "usuario", "cancelada_por"), pk=pk)
    return render(request, "ventas/detalle.html", {"venta": venta, "lineas": venta.lineas.select_related("producto")})


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
