from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ingrese el usuario", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Ingrese la contraseña"}),
    )
    remember_me = forms.BooleanField(required=False, widget=forms.CheckboxInput(), label="Recuerdame")
    
    def clean(self):
        cleaned = super().clean()
        login_input = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        return cleaned


class UsuarioForm(forms.ModelForm):
    """Alta y edición de usuarios con su rol. En edición la contraseña es opcional."""

    rol = forms.ChoiceField(
        label="Rol",
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    password1 = forms.CharField(
        label="Contraseña", required=False, strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña", required=False, strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        labels = {"username": "Usuario", "first_name": "Nombre", "last_name": "Apellidos",
                  "email": "Correo", "is_active": "Activo"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, editor=None, **kwargs):
        from .roles import ROLES, nombres_de_perfiles, rol_de

        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields["rol"].choices = [("", "Selecciona un rol")] + [(r, r) for r in ROLES] + [
            (n, f"{n} (perfil personalizado)") for n in nombres_de_perfiles()]
        if self.instance.pk:
            self.fields["rol"].initial = rol_de(self.instance)
            self.fields["password1"].help_text = "Déjala vacía para conservar la actual."
        else:
            self.fields["is_active"].initial = True

    def clean_email(self):
        return self.cleaned_data["email"].strip()

    def clean(self):
        from .roles import ADMINISTRAR, capacidades_de_rol

        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if not self.instance.pk and not p1:
            self.add_error("password1", "Define una contraseña para el usuario nuevo.")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(p1, self.instance if self.instance.pk else None)
                except ValidationError as error:
                    self.add_error("password1", error)
        # Un administrador no puede quitarse el acceso a sí mismo por accidente.
        if self.editor and self.instance.pk == self.editor.pk:
            if ADMINISTRAR not in capacidades_de_rol(datos.get("rol")) and not self.editor.is_superuser:
                self.add_error("rol", "No puedes quitarte a ti mismo el permiso de administración.")
            if not datos.get("is_active"):
                self.add_error("is_active", "No puedes desactivar tu propia cuenta.")
        return datos

    def save(self, commit=True):
        from .roles import ROLES, asignar_rol, nombres_de_perfiles

        usuario = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            usuario.set_password(self.cleaned_data["password1"])
        usuario.save()
        usuario.groups.remove(*usuario.groups.filter(name__in=list(ROLES) + nombres_de_perfiles()))
        asignar_rol(usuario, self.cleaned_data["rol"])
        return usuario


class PerfilAccesoForm(forms.Form):
    """Alta y edición de perfiles personalizados (un grupo con permisos por módulo)."""

    nombre = forms.CharField(label="Nombre del perfil", max_length=100,
                             widget=forms.TextInput(attrs={"class": "form-control"}))
    descripcion = forms.CharField(label="Descripción", max_length=200, required=False,
                                  widget=forms.TextInput(attrs={"class": "form-control"}))
    inventario = forms.BooleanField(label="Inventario (productos, movimientos, traspasos, recepción)", required=False,
                                    widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    compras = forms.BooleanField(label="Compras (proveedores y órdenes de compra)", required=False,
                                 widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    ventas = forms.BooleanField(label="Ventas (registrar ventas, clientes y prefacturas)", required=False,
                                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    administrar = forms.BooleanField(label="Administración (autorizar compras, negocios, usuarios, API)", required=False,
                                     widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil
        if perfil and not self.is_bound:
            self.initial = {"nombre": perfil.nombre, "descripcion": perfil.descripcion, "inventario": perfil.inventario,
                            "compras": perfil.compras, "ventas": perfil.ventas, "administrar": perfil.administrar}

    def clean_nombre(self):
        from django.contrib.auth.models import Group

        from .roles import ROLES

        nombre = self.cleaned_data["nombre"].strip()
        if nombre in ROLES:
            raise ValidationError("Ese nombre lo usa un rol del sistema. Elige otro.")
        existentes = Group.objects.filter(name__iexact=nombre)
        if self.perfil:
            existentes = existentes.exclude(pk=self.perfil.grupo_id)
        if existentes.exists():
            raise ValidationError("Ya existe un perfil o grupo con ese nombre.")
        return nombre

    def save(self):
        from django.contrib.auth.models import Group

        from .models import PerfilAcceso

        datos = self.cleaned_data
        if self.perfil:
            grupo = self.perfil.grupo
            grupo.name = datos["nombre"]
            grupo.save()
            perfil = self.perfil
        else:
            grupo = Group.objects.create(name=datos["nombre"])
            perfil = PerfilAcceso(grupo=grupo)
        perfil.descripcion = datos["descripcion"]
        for campo in ("inventario", "compras", "ventas", "administrar"):
            setattr(perfil, campo, datos[campo])
        perfil.save()
        return perfil
