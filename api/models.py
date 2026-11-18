import hashlib
import secrets

from django.conf import settings
from django.db import models

PREFIJO = "bmc_"


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenAPI(models.Model):
    """Credencial para sistemas externos. Solo se guarda el hash; el token se muestra una vez."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tokens_api", verbose_name="Usuario"
    )
    nombre = models.CharField(max_length=100, verbose_name="Nombre (para qué sistema es)")
    inicio = models.CharField(max_length=12, editable=False, verbose_name="Inicio del token")
    hash = models.CharField(max_length=64, unique=True, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Token de API"
        verbose_name_plural = "Tokens de API"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} ({self.inicio}…)"

    @classmethod
    def crear(cls, usuario, nombre):
        """Devuelve (objeto, token_en_claro). El token en claro no se puede recuperar después."""
        token = PREFIJO + secrets.token_urlsafe(32)
        objeto = cls.objects.create(usuario=usuario, nombre=nombre, inicio=token[:10], hash=_hash(token))
        return objeto, token

    @classmethod
    def buscar(cls, token):
        if not token or not token.startswith(PREFIJO):
            return None
        return cls.objects.select_related("usuario").filter(hash=_hash(token), activo=True).first()
