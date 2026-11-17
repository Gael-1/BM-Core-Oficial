from django.contrib import admin

from .models import Almacen, Existencia_Almacen, Medidas_Inventario, Producto, motivo_movimiento

admin.site.register(Producto)
admin.site.register(motivo_movimiento)
admin.site.register(Almacen)
admin.site.register(Medidas_Inventario)


@admin.register(Existencia_Almacen)
class ExistenciaAlmacenAdmin(admin.ModelAdmin):
    list_display = ("inventario", "almacen", "cantidad", "modificado")
    list_filter = ("almacen",)
