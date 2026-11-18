"""Roles del sistema (grupos de Django) y decoradores de acceso.

Los roles se crean solos después de `migrate`. Un superusuario puede hacer todo;
un usuario sin rol no puede entrar a ningún módulo.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied

ADMIN = "Administrador"
ALMACEN = "Almacenista"
COMPRAS = "Compras"
CONSULTA = "Consulta"

ROLES = (ADMIN, ALMACEN, COMPRAS, CONSULTA)


def crear_roles(sender=None, **kwargs):
    """Señal post_migrate: crea los grupos si no existen."""
    from django.contrib.auth.models import Group

    manager = Group.objects.using(kwargs.get("using", "default"))
    for nombre in ROLES:
        manager.get_or_create(name=nombre)


def asignar_rol(usuario, nombre):
    from django.contrib.auth.models import Group

    grupo, _ = Group.objects.get_or_create(name=nombre)
    usuario.groups.add(grupo)


def rol_de(usuario):
    """Nombre del primer rol del sistema que tiene el usuario (o cadena vacía)."""
    nombres = set(usuario.groups.values_list("name", flat=True))
    return next((r for r in ROLES if r in nombres), "")


def tiene_rol(usuario, roles):
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return usuario.groups.filter(name__in=roles).exists()


def rol_requerido(*roles):
    """Permite la vista solo a los roles indicados (en cualquier método HTTP)."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not tiene_rol(request.user, roles):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


# Quién puede qué
lectura = rol_requerido(*ROLES)                  # consultar pantallas y reportes
gestion_inventario = rol_requerido(ADMIN, ALMACEN)  # productos, movimientos, categorías, recepción
gestion_compras = rol_requerido(ADMIN, COMPRAS)     # proveedores y creación de órdenes
gestion_ventas = rol_requerido(ADMIN, ALMACEN)      # registrar ventas
solo_admin = rol_requerido(ADMIN)                   # autorizar/rechazar órdenes, negocios
