from django import forms
from django.forms import formset_factory

from inventory.models import Almacen, Producto
from proveedores.models import RegimenFiscal

from .facturacion import rfc_valido
from .models import ConfiguracionVentas, Cliente


class VentaForm(forms.Form):
    almacen = forms.ModelChoiceField(
        queryset=Almacen.objects.select_related("negocio").order_by("nombre"),
        label="Almacén de salida", empty_label="Selecciona un almacén",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(activo=True), required=False, label="Cliente fiscal (para facturar)",
        empty_label="Público en general", widget=forms.Select(attrs={"class": "form-select"}),
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


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "razon_social", "rfc", "regimen_fiscal", "codigo_postal", "uso_cfdi", "email", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "razon_social": forms.TextInput(attrs={"class": "form-control"}),
            "rfc": forms.TextInput(attrs={"class": "form-control", "style": "text-transform: uppercase;",
                                          "maxlength": "13"}),
            "regimen_fiscal": forms.Select(attrs={"class": "form-select"}),
            "codigo_postal": forms.TextInput(attrs={"class": "form-control", "maxlength": "5", "inputmode": "numeric"}),
            "uso_cfdi": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["regimen_fiscal"].queryset = RegimenFiscal.objects.filter(activo=True).order_by("codigo")
        self.fields["regimen_fiscal"].required = True
        self.fields["regimen_fiscal"].empty_label = "Selecciona un régimen"

    def clean_rfc(self):
        rfc = self.cleaned_data["rfc"].strip().upper()
        if not rfc_valido(rfc):
            raise forms.ValidationError("RFC no válido: 12 caracteres para empresas o 13 para personas físicas.")
        return rfc

    def clean_codigo_postal(self):
        cp = self.cleaned_data["codigo_postal"].strip()
        if not (len(cp) == 5 and cp.isdigit()):
            raise forms.ValidationError("El código postal debe tener 5 dígitos.")
        return cp


class ConfiguracionVentasForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionVentas
        fields = ["prefactura_automatica"]
        widgets = {"prefactura_automatica": forms.CheckboxInput(attrs={"class": "form-check-input"})}
