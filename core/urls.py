from django.conf import settings
import os

from django.conf.urls.static import static
from django.views.static import serve
from django.contrib import admin
from django.urls import include, path, re_path

urlpatterns = [
    path("admin/", admin.site.urls),

    # Dashboard
    path("", include(("home.urls", "home"), namespace="home")),

    # Módulos
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("inventory/", include(("inventory.urls", "inventory"), namespace="inventory")),
    path("reportes/", include(("reportes.urls", "reportes"), namespace="reportes")),
    path("proveedores/", include(("proveedores.urls", "proveedores"), namespace="proveedores")),
    path("negocios/", include(("negocio.urls", "negocio"), namespace="negocio")),
    path("categorias/", include(("categorias.urls", "categorias"), namespace="categorias")),
    path("compras/", include(("compra.urls", "compra"), namespace="compra")),
    path("navigation/", include(("navigation.urls", "navigation"), namespace="navigation")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif os.getenv("SERVE_MEDIA", "False") == "True":
    # Opción sencilla para despliegues pequeños (Docker). Con Nginx, que sirva /media/ él.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
