from django.urls import path

from accounts.roles import gestion_compras, gestion_inventario, lectura, solo_admin
from . import views

app_name = "compra"

urlpatterns = [
    path("", lectura(views.index), name="index"),
    path("configuracion/", solo_admin(views.configuracion), name="configuracion"),
    path("add/", gestion_compras(views.add), name="add"),
    path("view/<int:orden_id>/", lectura(views.view), name="view"),
    path("findProductos/", gestion_compras(views.findProductos), name="findProductos"),
    path("findNegocioRFC/", gestion_compras(views.findNegocioRFC), name="findNegocioRFC"),
    # Solo un administrador autoriza o rechaza; recibir mercancía es del almacén.
    path("autorizar_od/<int:orden_id>/", solo_admin(views.autorizar_oden), name="autorizar_od"),
    path("rechazar_od/<int:orden_id>/", solo_admin(views.rechazar_orden), name="rechazar_od"),
    path("completar_orden/<int:orden_id>/", gestion_inventario(views.completar_orden), name="completar_orden"),
]
