from django.conf import settings
from django.db import models


class EstatusVenta(models.TextChoices):
    COMPLETADA = "completada", "Completada"
    CANCELADA = "cancelada", "Cancelada"


class OrigenVenta(models.TextChoices):
    WEB = "web", "Captura en el sistema"
    API = "api", "Sistema externo (API)"


USOS_CFDI = [
    ("G01", "G01 · Adquisición de mercancías"),
    ("G03", "G03 · Gastos en general"),
    ("I04", "I04 · Equipo de cómputo y accesorios"),
    ("S01", "S01 · Sin efectos fiscales"),
]


class Cliente(models.Model):
    """Cliente con los datos fiscales necesarios para preparar una factura."""

    nombre = models.CharField(max_length=150, verbose_name="Nombre comercial")
    razon_social = models.CharField(max_length=200, verbose_name="Razón social")
    rfc = models.CharField(max_length=13, verbose_name="RFC")
    regimen_fiscal = models.ForeignKey(
        "proveedores.RegimenFiscal", on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Régimen fiscal",
    )
    codigo_postal = models.CharField(max_length=5, verbose_name="Código postal fiscal")
    email = models.EmailField(blank=True, verbose_name="Correo")
    uso_cfdi = models.CharField(max_length=3, choices=USOS_CFDI, default="G03", verbose_name="Uso del CFDI")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return f"{self.nombre} ({self.rfc})"


class Venta(models.Model):
    folio = models.CharField(max_length=30, unique=True, verbose_name="Folio")
    negocio = models.ForeignKey(
        "negocio.Negocio", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Negocio"
    )
    almacen = models.ForeignKey(
        "inventory.Almacen", on_delete=models.PROTECT, related_name="ventas", verbose_name="Almacén de salida"
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas", verbose_name="Cliente fiscal"
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


class Prefactura(models.Model):
    """Documento informativo con los datos de facturación de una venta. NO es un CFDI timbrado."""

    venta = models.OneToOneField(Venta, on_delete=models.PROTECT, related_name="prefactura")
    numero = models.CharField(max_length=20, unique=True)
    creada = models.DateTimeField(auto_now_add=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="prefacturas"
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    # Copia de emisor, receptor y conceptos al generarla: cambios posteriores no la alteran.
    datos = models.JSONField()

    class Meta:
        ordering = ["-creada"]
        verbose_name = "Prefactura"
        verbose_name_plural = "Prefacturas"

    def __str__(self):
        return self.numero
