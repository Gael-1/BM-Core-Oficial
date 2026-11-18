from django.conf import settings

def theme_context(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "userprofile", None)
        if profile:
            return {"theme_preference": profile.theme_preference}
    return {"theme_preference": None}

def session_timeout(request):
    return {
        "session_age": settings.SESSION_COOKIE_AGE,
    }


def permisos_context(request):
    """Banderas para mostrar u ocultar botones según el rol (el servidor igual valida)."""
    from .roles import ADMIN, ALMACEN, COMPRAS, tiene_rol

    usuario = request.user
    return {
        "puede_inventario": tiene_rol(usuario, (ADMIN, ALMACEN)),
        "puede_ventas": tiene_rol(usuario, (ADMIN, ALMACEN)),
        "puede_compras": tiene_rol(usuario, (ADMIN, COMPRAS)),
        "puede_admin": tiene_rol(usuario, (ADMIN,)),
    }
