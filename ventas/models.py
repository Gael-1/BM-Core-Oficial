from django.conf import settings
from django.db import models


class EstatusVenta(models.TextChoices):
    COMPLETADA = "completada", "Completada"
    CANCELADA = "cancelada", "Cancelada"


class OrigenVenta(models.TextChoices):
    WEB = "web", "Captura en el sistema"
    API = "api", "Sistema externo (API)"


class Venta(models.Model):
    folio = models.CharField(max_length=30, unique=True, verbose_name="Folio")
    negocio = models.ForeignKey(
        "negocio.Negocio", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Negocio"
    )
    almacen = models.ForeignKey(
        "inventory.Almacen", on_delete=models.PROTECT, related_name="ventas", verbose_name="Almacén de salida"
    )
    cliente_nombre = models.CharField(max_length=150, blank=True, verbose_name="Cliente")
    referencia_externa = models.CharField(
        max_length=80, null=True, blank=True, unique=True,
        verbose_name="Referencia externa",
        help_text="Identificador de la venta en el sistema de origen; evita registrarla dos veces.",
    )
    origen = models.CharField(max_length=10, choices=OrigenVenta.choices, default=OrigenVenta.WEB)
    estatus = models.CharField(max_length=12, choices=EstatusVenta.choices, default=EstatusVenta.COMPLETADA)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    comentarios = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ventas_registradas"
    )
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas_canceladas"
    )
    cancelada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-pk"]
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"

    def __str__(self):
        return f"{self.folio} (${self.total})"


class LineaVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="lineas")
    producto = models.ForeignKey("inventory.Producto", on_delete=models.PROTECT, related_name="lineas_venta")
    cantidad = models.FloatField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Línea de venta"
        verbose_name_plural = "Líneas de venta"

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad:g}"
