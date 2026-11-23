from django.urls import path

from accounts.roles import gestion_ventas, lectura, solo_admin

from . import views

app_name = "ventas"

urlpatterns = [
    path("", lectura(views.index), name="index"),
    path("nueva/", gestion_ventas(views.nueva), name="nueva"),
    path("<int:pk>/", lectura(views.detalle), name="detalle"),
    path("configuracion/", solo_admin(views.configuracion), name="configuracion"),
    path("clientes/", lectura(views.clientes), name="clientes"),
    path("clientes/nuevo/", gestion_ventas(views.cliente_add_edit), name="cliente_add"),
    path("clientes/<int:pk>/editar/", gestion_ventas(views.cliente_add_edit), name="cliente_edit"),
    path("<int:pk>/prefactura/generar/", gestion_ventas(views.generar_prefactura), name="prefactura_generar"),
    path("<int:pk>/prefactura/", lectura(views.prefactura), name="prefactura"),
    path("<int:pk>/prefactura.xml", lectura(views.prefactura_xml), name="prefactura_xml"),
    path("<int:pk>/cancelar/", solo_admin(views.cancelar), name="cancelar"),
]
