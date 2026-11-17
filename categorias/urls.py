from django.urls import path

from accounts.roles import gestion_inventario, lectura
from . import views

app_name = "categorias"

urlpatterns = [
    path("", lectura(views.index), name="index"),
    path("add/", gestion_inventario(views.add_edit), name="add"),
    path("edit/<int:pk>/", gestion_inventario(views.add_edit), name="edit"),
]
