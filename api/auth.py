from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.roles import INVENTARIO, VER, tiene_capacidad, tiene_rol

from .models import TokenAPI


def _error(estado, mensaje):
    return JsonResponse({"error": mensaje}, status=estado)


def token_requerido(*roles, capacidad=VER):
    """Autentica con `Authorization: Bearer <token>` y exige la capacidad (o alguno de los roles) del usuario del token."""

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
            permitido = tiene_rol(token.usuario, roles) if roles else tiene_capacidad(token.usuario, capacidad)
            if not permitido:
                return _error(403, "El usuario de este token no tiene permiso para esta operación.")
            ahora = timezone.now()
            if token.ultimo_uso is None or (ahora - token.ultimo_uso).total_seconds() > 60:
                TokenAPI.objects.filter(pk=token.pk).update(ultimo_uso=ahora)
            request.user = token.usuario
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


lectura_api = token_requerido(capacidad=VER)
escritura_api = token_requerido(capacidad=INVENTARIO)
