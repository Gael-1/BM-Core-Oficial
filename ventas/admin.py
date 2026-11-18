from django.contrib import admin

from .models import LineaVenta, Venta


class LineaInline(admin.TabularInline):
    model = LineaVenta
    extra = 0
    readonly_fields = ("producto", "cantidad", "precio_unitario", "subtotal")
    can_delete = False


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("folio", "fecha", "almacen", "total", "estatus", "origen")
    list_filter = ("estatus", "origen")
    readonly_fields = ("folio", "total", "fecha")
    inlines = [LineaInline]
