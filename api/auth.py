from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.roles import ADMIN, ALMACEN, tiene_rol, ROLES

from .models import TokenAPI


def _error(estado, mensaje):
    return JsonResponse({"error": mensaje}, status=estado)


def token_requerido(*roles):
    """Autentica con `Authorization: Bearer <token>` y exige alguno de los roles del usuario del token."""
    roles = roles or ROLES

    def decorador(vista):
        @csrf_exempt  # sin cookies de sesión no hay riesgo CSRF: la credencial va en la cabecera
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            cabecera = request.headers.get("Authorization", "")
            esquema, _, valor = cabecera.partition(" ")
            if esquema.lower() != "bearer" or not valor.strip():
                return _error(401, "Falta el token. Usa la cabecera Authorization: Bearer <token>.")
            token = TokenAPI.buscar(valor.strip())
            if token is None or not token.usuario.is_active:
                return _error(401, "Token inválido o revocado.")
            if not tiene_rol(token.usuario, roles):
                return _error(403, "El usuario de este token no tiene permiso para esta operación.")
            ahora = timezone.now()
            if token.ultimo_uso is None or (ahora - token.ultimo_uso).total_seconds() > 60:
                TokenAPI.objects.filter(pk=token.pk).update(ultimo_uso=ahora)
            request.user = token.usuario
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


lectura_api = token_requerido()
escritura_api = token_requerido(ADMIN, ALMACEN)
