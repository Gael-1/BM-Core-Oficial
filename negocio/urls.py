from django.urls import path

from accounts.roles import lectura, solo_admin
from . import views

app_name = "negocio"

urlpatterns = [
    path("", lectura(views.index), name="index"),
    path("add/", solo_admin(views.add), name="add"),
    path("edit/<int:pk>/", solo_admin(views.edit), name="edit"),
    path("view_inventario/<int:pk>/", lectura(views.view_inventario), name="view_inventario"),
]
