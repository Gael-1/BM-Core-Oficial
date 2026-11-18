from django.urls import path

from accounts.roles import gestion_ventas, lectura, solo_admin

from . import views

app_name = "ventas"

urlpatterns = [
    path("", lectura(views.index), name="index"),
    path("nueva/", gestion_ventas(views.nueva), name="nueva"),
    path("<int:pk>/", lectura(views.detalle), name="detalle"),
    path("<int:pk>/cancelar/", solo_admin(views.cancelar), name="cancelar"),
]
