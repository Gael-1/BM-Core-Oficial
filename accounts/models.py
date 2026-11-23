from django.db import models

# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    theme_preference = models.CharField(max_length=20, choices=[('light', 'Light'), ('dark', 'Dark')], default='light')

    def __str__(self):
        return f"{self.user.username} - {self.theme_preference}"


class PerfilAcceso(models.Model):
    """Perfil personalizado: un grupo de Django con permisos elegidos módulo por módulo."""

    grupo = models.OneToOneField("auth.Group", on_delete=models.CASCADE, related_name="perfil_acceso")
    descripcion = models.CharField(max_length=200, blank=True)
    inventario = models.BooleanField("Inventario (productos, movimientos, traspasos, recepción)", default=False)
    compras = models.BooleanField("Compras (proveedores y órdenes de compra)", default=False)
    ventas = models.BooleanField("Ventas (registrar ventas, clientes y prefacturas)", default=False)
    administrar = models.BooleanField("Administración (autorizar compras, negocios, usuarios, API)", default=False)

    class Meta:
        ordering = ["grupo__name"]

    @property
    def nombre(self):
        return self.grupo.name

    def capacidades(self):
        """Todo perfil puede consultar; lo demás depende de las casillas marcadas."""
        capacidades = {"ver"}
        for campo in ("inventario", "compras", "ventas", "administrar"):
            if getattr(self, campo):
                capacidades.add(campo)
        return capacidades

    def __str__(self):
        return self.nombre
