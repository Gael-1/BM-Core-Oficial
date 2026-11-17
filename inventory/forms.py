import math

from django import forms
from .models import Categoria, Producto, Almacen, motivo_movimiento
from django.forms.widgets import ClearableFileInput


class CustomClearableFileInput(ClearableFileInput):
    template_name = "widgets/custom_clearable_file_input.html"


class addProductForm(forms.ModelForm):
    # Campo para escaneo por Lector / QR
    codigo_barras = forms.CharField(
        required=False,
        label="Código de Barras / QR",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Escanea o ingresa el código",
                "autocomplete": "off",
                "autofocus": "autofocus",
            }
        ),
    )

    nueva_categoria = forms.CharField(
        required=False,
        max_length=100,
        label="O escribe una categoría nueva",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej. Lácteos (si ya existe, se usa la existente)",
                "autocomplete": "off",
            }
        ),
    )

    # Selección de Almacén para trazabilidad
    almacen = forms.ModelChoiceField(
        queryset=Almacen.objects.all(),
        required=False,
        label="Almacén / Ubicación",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    addCantidad = forms.BooleanField(
        required=False,
        label="¿Quieres añadir cantidad?",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    cantidad = forms.FloatField(
        required=False,
        label="Cantidad inicial",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "0"}),
    )
    cantidad_actual = forms.FloatField(
        required=False,
        label="Cantidad actual",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "0", "readonly": "readonly"}
        ),
    )
    cantidad_nueva = forms.FloatField(
        required=False,
        label="Cantidad nueva",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "0"}),
    )

    class Meta:
        model = Producto
        fields = [
            "sku",
            "codigo_barras",
            "nombre",
            "categoria_id",
            "descripcion",
            "precio",
            "stock_min",
            "imagen",
            "medida",
        ]
        widgets = {
            "sku": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Código SKU",
                    "autocomplete": "off",
                }
            ),
            "nombre": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre del producto"}
            ),
            "categoria_id": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Descripción"}
            ),
            "precio": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"}
            ),
            "stock_min": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "0"}
            ),
            "imagen": CustomClearableFileInput(attrs={"class": "form-control"}),
            "medida": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria_id"].empty_label = "Selecciona una categoría"
        # Se puede elegir una existente o escribir una nueva; clean() exige al menos una.
        self.fields["categoria_id"].required = False
        self.fields["medida"].empty_label = "Selecciona una medida"
        self.fields["almacen"].empty_label = "Selecciona un almacén"

    field_order = [
        "sku", "codigo_barras", "nombre", "categoria_id", "nueva_categoria",
        "descripcion", "precio", "stock_min", "imagen", "medida",
    ]

    def clean_nueva_categoria(self):
        return " ".join((self.cleaned_data.get("nueva_categoria") or "").split())

    def clean_codigo_barras(self):
        codigo = self.cleaned_data.get("codigo_barras")
        if codigo:
            codigo = codigo.strip()
            qs = Producto.objects.filter(codigo_barras=codigo)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Este código de barras ya pertenece a otro producto registrado."
                )
        return codigo or None

    def clean(self):
        datos = super().clean()
        medida = datos.get("medida")
        for campo in ("cantidad", "cantidad_nueva", "stock_min"):
            valor = datos.get(campo)
            if valor is None:
                continue
            if not math.isfinite(valor) or valor < 0:
                self.add_error(campo, "Ingresa una cantidad finita mayor o igual a cero.")
            elif medida and not medida.permite_decimales and not float(valor).is_integer():
                self.add_error(campo, "Esta unidad de medida solo permite cantidades enteras.")
        if not self.instance.pk and datos.get("addCantidad") and datos.get("cantidad") is None:
            self.add_error("cantidad", "Ingresa la cantidad inicial.")
        if self.instance.pk and datos.get("cantidad_nueva") is not None and datos.get("cantidad_actual") is None:
            self.add_error("cantidad_actual", "Recarga la página para consultar la existencia actual.")

        nueva = datos.get("nueva_categoria")
        if nueva and not datos.get("categoria_id"):
            if not self.errors:  # solo se crea la categoría si lo demás está bien
                categoria = Categoria.objects.filter(nombre__iexact=nueva).first()
                if categoria is None:
                    categoria = Categoria.objects.create(nombre=nueva)
                elif not categoria.activo:
                    categoria.activo = True
                    categoria.save(update_fields=["activo"])
                datos["categoria_id"] = categoria
        elif not datos.get("categoria_id") and not self.errors.get("categoria_id"):
            self.add_error("categoria_id", "Selecciona una categoría o escribe una nueva.")
        return datos


class MovimientoForm(forms.Form):
    """Registro manual de una entrada o salida de existencias."""

    TIPOS = (("ENTRADA", "Entrada"), ("SALIDA", "Salida"))

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        label="Producto",
        empty_label="Selecciona un producto",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tipo_movimiento = forms.ChoiceField(
        choices=TIPOS,
        label="Tipo de movimiento",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cantidad = forms.FloatField(
        label="Cantidad",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any", "placeholder": "0"}),
    )
    almacen = forms.ModelChoiceField(
        queryset=Almacen.objects.order_by("nombre"),
        required=False,
        label="Almacén",
        empty_label="Almacén predeterminado del producto",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    motivo = forms.ModelChoiceField(
        queryset=motivo_movimiento.objects.filter(activo=True).order_by("nombre"),
        label="Motivo",
        empty_label="Selecciona un motivo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comentarios = forms.CharField(
        required=False,
        max_length=255,
        label="Comentarios",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def clean(self):
        datos = super().clean()
        cantidad = datos.get("cantidad")
        producto = datos.get("producto")
        if cantidad is None:
            return datos
        if not math.isfinite(cantidad) or cantidad <= 0:
            self.add_error("cantidad", "Ingresa una cantidad finita mayor a cero.")
        elif producto and producto.medida and not producto.medida.permite_decimales \
                and not float(cantidad).is_integer():
            self.add_error("cantidad", "Esta unidad de medida solo permite cantidades enteras.")
        return datos


class TraspasoForm(forms.Form):
    """Mueve existencias de un almacén a otro. El total del producto no cambia."""

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        label="Producto",
        empty_label="Selecciona un producto",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    almacen_origen = forms.ModelChoiceField(
        queryset=Almacen.objects.order_by("nombre"),
        required=False,
        label="Almacén origen",
        empty_label="Sin asignar",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    almacen_destino = forms.ModelChoiceField(
        queryset=Almacen.objects.order_by("nombre"),
        label="Almacén destino",
        empty_label="Selecciona el destino",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cantidad = forms.FloatField(
        label="Cantidad",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any", "placeholder": "0"}),
    )
    comentarios = forms.CharField(
        required=False,
        max_length=255,
        label="Comentarios",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def clean(self):
        datos = super().clean()
        origen = datos.get("almacen_origen")
        destino = datos.get("almacen_destino")
        cantidad = datos.get("cantidad")
        producto = datos.get("producto")
        if destino and origen and origen.pk == destino.pk:
            self.add_error("almacen_destino", "El destino debe ser distinto del origen.")
        if cantidad is not None:
            if not math.isfinite(cantidad) or cantidad <= 0:
                self.add_error("cantidad", "Ingresa una cantidad finita mayor a cero.")
            elif producto and producto.medida and not producto.medida.permite_decimales \
                    and not float(cantidad).is_integer():
                self.add_error("cantidad", "Esta unidad de medida solo permite cantidades enteras.")
        return datos


class AlmacenForm(forms.ModelForm):
    class Meta:
        model = Almacen
        fields = ["nombre", "direccion", "negocio", "es_principal"]
        labels = {"negocio": "Negocio / sucursal (opcional)"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del almacén"}),
            "direccion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dirección"}),
            "negocio": forms.Select(attrs={"class": "form-select"}),
            "es_principal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["negocio"].required = False
        self.fields["negocio"].empty_label = "General (sin negocio)"

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetidos = Almacen.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise forms.ValidationError("Ya existe un almacén con ese nombre.")
        return nombre
