from django import forms
from django.forms import formset_factory

from inventory.models import Almacen, Producto


class VentaForm(forms.Form):
    almacen = forms.ModelChoiceField(
        queryset=Almacen.objects.select_related("negocio").order_by("nombre"),
        label="Almacén de salida", empty_label="Selecciona un almacén",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cliente_nombre = forms.CharField(
        required=False, max_length=150, label="Cliente (opcional)",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Público en general"}),
    )
    comentarios = forms.CharField(
        required=False, max_length=255, label="Comentarios",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class LineaVentaForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by("nombre"), required=False,
        empty_label="—", widget=forms.Select(attrs={"class": "form-select"}),
    )
    cantidad = forms.FloatField(
        required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any", "min": "0"}),
    )
    precio_unitario = forms.DecimalField(
        required=False, min_value=0, max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0",
                                        "placeholder": "Precio del producto"}),
    )

    def clean(self):
        datos = super().clean()
        producto, cantidad = datos.get("producto"), datos.get("cantidad")
        if producto is None and cantidad is None and datos.get("precio_unitario") is None:
            return datos  # fila vacía
        if producto is None:
            self.add_error("producto", "Elige el producto.")
        if cantidad is None or cantidad <= 0:
            self.add_error("cantidad", "Indica una cantidad mayor a cero.")
        return datos


LineaVentaFormSet = formset_factory(LineaVentaForm, extra=6, max_num=20, validate_max=True)
