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
    """Nombre del rol del usuario: primero los del sistema y, si no, un perfil personalizado (o cadena vacía)."""
    nombres = set(usuario.groups.values_list("name", flat=True))
    base = next((r for r in ROLES if r in nombres), "")
    if base:
        return base
    return next(iter(sorted(nombres & set(nombres_de_perfiles()))), "")


def nombres_de_perfiles():
    """Nombres de los perfiles personalizados creados por el administrador."""
    from django.contrib.auth.models import Group

    return list(Group.objects.filter(perfil_acceso__isnull=False).order_by("name").values_list("name", flat=True))


def tiene_rol(usuario, roles):
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return usuario.groups.filter(name__in=roles).exists()


# --- Capacidades: lo que se puede hacer, venga del rol del sistema o de un perfil personalizado ---
VER, INVENTARIO, COMPRAS_CAP, VENTAS, ADMINISTRAR = "ver", "inventario", "compras", "ventas", "administrar"
CAPACIDADES = (VER, INVENTARIO, COMPRAS_CAP, VENTAS, ADMINISTRAR)
CAPACIDADES_BASE = {
    ADMIN: set(CAPACIDADES),
    ALMACEN: {VER, INVENTARIO, VENTAS},
    COMPRAS: {VER, COMPRAS_CAP},
    CONSULTA: {VER},
}


def capacidades_de_rol(nombre):
    """Capacidades de un rol del sistema o de un perfil personalizado, por su nombre."""
    if nombre in CAPACIDADES_BASE:
        return set(CAPACIDADES_BASE[nombre])
    from .models import PerfilAcceso

    perfil = PerfilAcceso.objects.filter(grupo__name=nombre).first()
    return perfil.capacidades() if perfil else set()


def capacidades_de(usuario):
    """Conjunto de capacidades del usuario. Un superusuario las tiene todas."""
    if not usuario.is_authenticated:
        return set()
    if usuario.is_superuser:
        return set(CAPACIDADES)
    from .models import PerfilAcceso

    nombres = set(usuario.groups.values_list("name", flat=True))
    capacidades = set()
    for nombre in nombres & set(CAPACIDADES_BASE):
        capacidades |= CAPACIDADES_BASE[nombre]
    for perfil in PerfilAcceso.objects.filter(grupo__name__in=nombres):
        capacidades |= perfil.capacidades()
    return capacidades


def tiene_capacidad(usuario, capacidad):
    return capacidad in capacidades_de(usuario)


def capacidad_requerida(capacidad):
    """Permite la vista solo a quien tenga la capacidad (por rol del sistema o perfil personalizado)."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not tiene_capacidad(request.user, capacidad):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


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
lectura = capacidad_requerida(VER)                  # consultar pantallas y reportes
gestion_inventario = capacidad_requerida(INVENTARIO)  # productos, movimientos, categorías, recepción
gestion_compras = capacidad_requerida(COMPRAS_CAP)    # proveedores y creación de órdenes
gestion_ventas = capacidad_requerida(VENTAS)          # registrar ventas
solo_admin = capacidad_requerida(ADMINISTRAR)         # autorizar/rechazar órdenes, negocios, usuarios
