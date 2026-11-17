from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.templatetags.static import static

from categorias.models import Categoria


class Almacen(models.Model):
    """Model definition for Almacen / Ubicación."""
    nombre = models.CharField(verbose_name="Nombre del Almacén", max_length=100)
    direccion = models.CharField(verbose_name="Dirección", max_length=255, blank=True, null=True)
    es_principal = models.BooleanField(default=False, verbose_name="¿Es Almacén Principal?")
    negocio = models.ForeignKey(
        "negocio.Negocio",
        on_delete=models.CASCADE,
        related_name="almacenes",
        null=True,
        blank=True,
        verbose_name="Negocio / Sucursal"
    )

    class Meta:
        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"

    def __str__(self):
        return f"{self.nombre} ({self.negocio.nombre if self.negocio else 'General'})"


class Producto(models.Model):
    """Model definition for Producto."""

    categoria_id = models.ForeignKey(
        Categoria, verbose_name="Categoria", on_delete=models.CASCADE
    )
    sku = models.CharField(
        verbose_name="Codigo SKU", max_length=100, unique=True, blank=True
    )
    codigo_barras = models.CharField(
        verbose_name="Código de Barras / QR",
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        db_index=True
    )
    nombre = models.CharField(
        verbose_name="Nombre", max_length=100, blank=False, null=False
    )
    descripcion = models.TextField(
        verbose_name="Descripcion", blank=True, null=True, max_length=255
    )
    precio = models.DecimalField(
        verbose_name="Precio",
        max_digits=11,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    medida = models.ForeignKey(
        "Medidas_Inventario",
        verbose_name="Medida",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    stock_min = models.FloatField(verbose_name="Stock minimo", default=0)
    creado = models.DateTimeField(verbose_name="Fecha de Creacion", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="productos_creados",
        verbose_name="Creado por",
    )
    modificado = models.DateTimeField(verbose_name="Fecha de Modificado", auto_now=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="productos_modificados",
        verbose_name="Modificado Por",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    imagen = models.ImageField(
        upload_to="img/inventory/", blank=True, null=True, verbose_name="Imagen"
    )

    @property
    def stock_actual(self):
        if hasattr(self, 'inventario'):
            return self.inventario.cantidad
        return 0.0

    @property
    def necesita_reabastecimiento(self):
        return self.stock_actual <= self.stock_min

    def get_imagen_url(self):
        if self.imagen and hasattr(self.imagen, "url"):
            return self.imagen.url
        return static("img/default.png")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["modificado"]

    def save(self, *args, **kwargs):
        if self.medida and not self.medida.permite_decimales:
            self.stock_min = int(self.stock_min)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Inventario_Producto(models.Model):
    """Model definition for Inventario_Productos."""

    producto_id = models.OneToOneField(
        Producto,
        verbose_name="Producto",
        on_delete=models.CASCADE,
        related_name="inventario",
    )
    almacen = models.ForeignKey(
        Almacen,
        verbose_name="Almacén",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventarios_productos"
    )
    cantidad = models.FloatField(
        verbose_name="Cantidad", validators=[MinValueValidator(0)]
    )
    creado = models.DateTimeField(verbose_name="Fecha de Creacion", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventarios_creados",
        verbose_name="Creado por",
    )
    modificado = models.DateTimeField(verbose_name="Fecha de Modificado", auto_now=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventarios_modificados",
        verbose_name="Modificado Por",
    )
    negocio = models.ForeignKey(
        "negocio.Negocio",
        verbose_name="Negocio",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Inventario_Productos"
        verbose_name_plural = "Inventario_Productos"

    def save(self, *args, **kwargs):
        medida = getattr(self.producto_id, "medida", None)
        if medida and not medida.permite_decimales:
            self.cantidad = int(self.cantidad)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto_id.nombre} - {self.cantidad}"


class Registro_Inventario(models.Model):
    """Model definition for Registro_Inventario."""

    TIPOS_MOVIMIENTO = (
        ("ENTRADA", "Entrada"),
        ("SALIDA", "Salida"),
        ("TRASPASO", "Traspaso entre Almacenes"),
    )

    inventario_producto_id = models.ForeignKey(
        Inventario_Producto,
        verbose_name="Producto",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    almacen_origen = models.ForeignKey(
        Almacen,
        verbose_name="Almacén Origen",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_origen"
    )
    almacen_destino = models.ForeignKey(
        Almacen,
        verbose_name="Almacén Destino",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_destino"
    )
    tipo_movimiento = models.CharField(
        verbose_name="Tipo de Movimiento", max_length=10, choices=TIPOS_MOVIMIENTO
    )
    cantidad_nueva = models.FloatField(
        verbose_name="Cantidad", validators=[MinValueValidator(1)]
    )
    cantidad_anterior = models.FloatField(
        verbose_name="Cantidad Anterior",
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    creado = models.DateTimeField(
        verbose_name="Fecha del Movimiento", auto_now_add=True
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registros_inventario_creados",
        verbose_name="Creado por",
    )
    comentarios = models.TextField(
        verbose_name="Comentarios", blank=True, null=True, max_length=255
    )
    orden_compra = models.ForeignKey(
        "compra.OrdenDeCompra", on_delete=models.CASCADE, null=True, blank=True
    )
    motivo = models.ForeignKey(
        "inventory.motivo_movimiento",
        verbose_name="Motivo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Registro_Inventario"
        verbose_name_plural = "Registro_Inventarios"

    def save(self, *args, **kwargs):
        producto = getattr(self.inventario_producto_id, "producto_id", None)
        medida = getattr(producto, "medida", None)

        if medida and not medida.permite_decimales:
            self.cantidad_nueva = int(self.cantidad_nueva)
            if self.cantidad_anterior is not None:
                self.cantidad_anterior = int(self.cantidad_anterior)

        super().save(*args, **kwargs)

    def __str__(self):
        prod_nombre = self.inventario_producto_id.producto_id.nombre if self.inventario_producto_id else "N/A"
        return f"{self.tipo_movimiento} - {prod_nombre} ({self.cantidad_nueva})"


class Medidas_Inventario(models.Model):
    """Model definition for Medidas_Inventario."""

    nombre = models.CharField(
        verbose_name="Nombre de la Medida", max_length=50, unique=True
    )
    abreviatura = models.TextField(
        verbose_name="Abreviatura", blank=True, null=True, max_length=255
    )
    permite_decimales = models.BooleanField(
        default=False, verbose_name="Permite Decimales"
    )

    class Meta:
        verbose_name = "Medida de Inventario"
        verbose_name_plural = "Medidas de Inventario"

    def __str__(self):
        return self.nombre


class Negocio_Inventario(models.Model):
    negocio = models.ForeignKey(
        "negocio.Negocio",
        verbose_name="Negocio",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    producto = models.ForeignKey(
        "inventory.Producto",
        on_delete=models.CASCADE,
        verbose_name="Producto",
        null=True,
        blank=True,
    )
    almacen = models.ForeignKey(
        Almacen,
        verbose_name="Almacén Asignado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    cantidad = models.FloatField(
        verbose_name="Cantidad en Inventario",
        validators=[MinValueValidator(0)],
        blank=False,
        null=False,
    )
    creado = models.DateTimeField(verbose_name="Fecha de Creación", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="negocios_inventario_creados",
        verbose_name="Creado por",
    )
    modificado = models.DateTimeField(
        verbose_name="Fecha de Modificación", auto_now=True
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="negocios_inventario_modificados",
        verbose_name="Modificado Por",
    )
    activo = models.BooleanField(default=True, verbose_name="Inventario Activo")

    class Meta:
        verbose_name = "Negocio Inventario"
        verbose_name_plural = "Negocios Inventario"

    def __str__(self):
        return f"Inventario de {self.negocio.nombre if self.negocio else 'N/A'}"


class Registro_Negocio_Inventario(models.Model):
    negocio_inventario = models.ForeignKey(
        Negocio_Inventario,
        verbose_name="Negocio Inventario",
        on_delete=models.CASCADE,
        related_name="registros",
    )
    cantidad_nueva = models.FloatField(
        verbose_name="Cantidad Nueva",
        validators=[MinValueValidator(0)],
        blank=False,
        null=False,
    )
    cantidad_anterior = models.FloatField(
        verbose_name="Cantidad Anterior",
        validators=[MinValueValidator(0)],
        blank=False,
        null=False,
    )
    creado = models.DateTimeField(
        verbose_name="Fecha del Movimiento", auto_now_add=True
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registros_negocio_inventario_creados",
        verbose_name="Creado por",
    )
    comentarios = models.TextField(
        verbose_name="Comentarios", blank=True, null=True, max_length=255
    )

    class Meta:
        verbose_name = "Registro Negocio Inventario"
        verbose_name_plural = "Registros Negocio Inventario"

    def __str__(self):
        return f"Registro de {self.negocio_inventario.negocio.nombre if self.negocio_inventario.negocio else 'N/A'} - {self.cantidad_nueva}"


class motivo_movimiento(models.Model):
    nombre = models.CharField(
        verbose_name="Nombre del Motivo", max_length=100, unique=True
    )
    descripcion = models.TextField(
        verbose_name="Descripcion", blank=True, null=True, max_length=255
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Motivo de Movimiento"
        verbose_name_plural = "Motivos de Movimiento"

    def __str__(self):
        return self.nombre