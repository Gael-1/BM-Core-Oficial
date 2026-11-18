from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views
from .auth import escritura_api, lectura_api


@csrf_exempt
def movimientos(request):
    """GET lo puede usar cualquier rol; POST solo administrador y almacenista."""
    vista = escritura_api(views.movimientos) if request.method == "POST" else lectura_api(views.movimientos)
    return vista(request)


urlpatterns = [
    path("productos/", lectura_api(views.productos), name="productos"),
    path("productos/<int:pk>/", lectura_api(views.producto_detalle), name="producto"),
    path("almacenes/", lectura_api(views.almacenes), name="almacenes"),
    path("movimientos/", movimientos, name="movimientos"),
]
