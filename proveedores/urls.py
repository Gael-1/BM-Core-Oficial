from django.urls import path

from accounts.roles import gestion_compras, lectura
from . import views

app_name = "proveedores"

urlpatterns = [
    path("", lectura(views.index), name="index"),
    path("add/", gestion_compras(views.add), name="add"),
    path("edit/<int:pk>/", gestion_compras(views.edit), name="edit"),
    path("asignar_productos/<int:pk>/", gestion_compras(views.add_edit_producto), name="asignar_productos"),
]
