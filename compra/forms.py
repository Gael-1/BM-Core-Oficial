import json
from decimal import Decimal, InvalidOperation

from django import forms
from proveedores.models import ProductosProveedor
from .models import OrdenDeCompra, ProductoEnOrden


class OrdenDeCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenDeCompra
        fields = [
            "numero_de_orden",
            "subtotal",
            "total",
            "justificacion",
            "negocio",
            "proveedor",
        ]
        widgets = {
            "numero_de_orden": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Primero seleccione el negocio",
                    "autocomplete": "off",
                    "readonly": "readonly",
                }
            ),
            "subtotal": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Subtotal",
                    "readonly": "readonly",
                }
            ),
            "total": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Total",
                    "readonly": "readonly",
                }
            ),
            "justificacion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Justificación",
                }
            ),
            "negocio": forms.Select(attrs={"class": "form-select"}),
            "proveedor": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("numero_de_orden", "subtotal", "total"):
            self.fields[campo].required = False
        self.fields["numero_de_orden"].widget.attrs["placeholder"] = "Se asignará al guardar"
        self.fields["proveedor"].queryset = self.fields["proveedor"].queryset.filter(activo=True)
        self.fields["negocio"].empty_label = "Selecciona un negocio"
        self.fields["proveedor"].empty_label = "Selecciona un proveedor"


    def clean(self):
        datos = super().clean()
        self.lineas = []
        try:
            productos = json.loads(self.data.get("productos_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError("La lista de productos no es válida.")
        if not isinstance(productos, list) or not productos:
            raise forms.ValidationError("Agrega al menos un producto a la orden.")
        if len(productos) > 200:
            raise forms.ValidationError("La orden admite hasta 200 productos.")
        proveedor = datos.get("proveedor")
        if not proveedor:
            return datos
        vistos = set()
        total = Decimal("0.00")
        for item in productos:
            try:
                if not isinstance(item, dict):
                    raise ValueError
                producto_id = int(str(item["producto_id"]))
                cantidad = Decimal(str(item["cantidad"]))
                if not cantidad.is_finite() or cantidad <= 0 or cantidad != cantidad.to_integral_value() or cantidad > 2147483647:
                    raise ValueError
            except (KeyError, ValueError, TypeError, InvalidOperation):
                raise forms.ValidationError("Cada producto necesita una cantidad entera mayor que cero.")
            if producto_id in vistos:
                raise forms.ValidationError("Cada producto debe aparecer una sola vez en la orden.")
            vistos.add(producto_id)
            relacion = ProductosProveedor.objects.select_related("producto").filter(
                proveedor=proveedor, producto_id=producto_id, activo=True, producto__activo=True,
            ).first()
            if not relacion:
                raise forms.ValidationError("Un producto no está disponible con el proveedor seleccionado.")
            precio = relacion.precio
            if not precio.is_finite() or precio <= 0:
                raise forms.ValidationError("El proveedor debe tener un precio positivo para cada producto.")
            subtotal = (precio * cantidad).quantize(Decimal("0.01"))
            total += subtotal
            if total >= Decimal("10000000000"):
                raise forms.ValidationError("El importe de la orden supera el máximo permitido.")
            self.lineas.append({"producto": relacion.producto, "cantidad": int(cantidad),
                                "precio_unitario": precio, "subtotal": subtotal})
        # Los precios y totales del navegador solo son una vista previa.
        datos["subtotal"] = datos["total"] = total
        return datos


class ProductoEnOrdenForm(forms.ModelForm):
    class Meta:
        model = ProductoEnOrden
        fields = ["producto", "cantidad", "precio_unitario"]
        widgets = {
            "producto": forms.Select(attrs={"class": "form-select"}),
            "cantidad": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Cantidad"}
            ),
            "precio_unitario": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Precio Unitario"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].empty_label = "Selecciona un producto"


formset = forms.inlineformset_factory(
    OrdenDeCompra,
    ProductoEnOrden,
    form=ProductoEnOrdenForm,
    extra=1,
    can_delete=False,
)
