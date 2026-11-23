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
    """Banderas para mostrar u ocultar botones según los permisos (el servidor igual valida)."""
    from .roles import ADMINISTRAR, COMPRAS_CAP, INVENTARIO, VENTAS, capacidades_de

    capacidades = capacidades_de(request.user)
    return {
        "puede_inventario": INVENTARIO in capacidades,
        "puede_ventas": VENTAS in capacidades,
        "puede_compras": COMPRAS_CAP in capacidades,
        "puede_admin": ADMINISTRAR in capacidades,
    }
