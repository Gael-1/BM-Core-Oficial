from django.urls import path

from accounts.roles import gestion_inventario, lectura
from . import views

app_name = "inventory"

urlpatterns = [
    # Productos
    path("", lectura(views.productos), name="productos"),

    # Agregar / editar producto
    path("agregar/", gestion_inventario(views.add), name="add"),
    path("editar/<int:pk>/", gestion_inventario(views.edit), name="edit"),

    # Buscar producto por código de barras / SKU
    path("buscar-codigo/", lectura(views.buscar_producto_codigo), name="buscar_codigo"),

    # Alertas de reabastecimiento
    path("alertas/", lectura(views.alertas_reabastecimiento), name="alertas"),

    # Entradas / salidas e historial
    path("movimientos/", lectura(views.historial_movimientos), name="historial"),
    path("movimientos/nuevo/", gestion_inventario(views.registrar_movimiento), name="movimiento"),

    # Inventario por almacén
    path("almacen/", lectura(views.inventario_por_almacen), name="inventario_por_almacen"),

    # Almacenes y traspasos
    path("almacenes/", lectura(views.almacenes), name="almacenes"),
    path("almacenes/nuevo/", gestion_inventario(views.almacen_add_edit), name="almacen_add"),
    path("almacenes/<int:pk>/editar/", gestion_inventario(views.almacen_add_edit), name="almacen_edit"),
    path("traspasos/nuevo/", gestion_inventario(views.registrar_traspaso), name="traspaso"),
]
