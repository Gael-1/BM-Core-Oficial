from django.contrib import admin

from .models import Almacen, Existencia_Almacen, Producto, motivo_movimiento

admin.site.register(Producto)
admin.site.register(motivo_movimiento)
admin.site.register(Almacen)


@admin.register(Existencia_Almacen)
class ExistenciaAlmacenAdmin(admin.ModelAdmin):
    list_display = ("inventario", "almacen", "cantidad", "modificado")
    list_filter = ("almacen",)
