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
        from .roles import ROLES, rol_de

        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields["rol"].choices = [("", "Selecciona un rol")] + [(r, r) for r in ROLES]
        if self.instance.pk:
            self.fields["rol"].initial = rol_de(self.instance)
            self.fields["password1"].help_text = "Déjala vacía para conservar la actual."
        else:
            self.fields["is_active"].initial = True

    def clean_email(self):
        return self.cleaned_data["email"].strip()

    def clean(self):
        from .roles import ADMIN

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
            if datos.get("rol") != ADMIN and not self.editor.is_superuser:
                self.add_error("rol", "No puedes quitarte el rol de Administrador a ti mismo.")
            if not datos.get("is_active"):
                self.add_error("is_active", "No puedes desactivar tu propia cuenta.")
        return datos

    def save(self, commit=True):
        from .roles import ROLES, asignar_rol

        usuario = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            usuario.set_password(self.cleaned_data["password1"])
        usuario.save()
        usuario.groups.remove(*usuario.groups.filter(name__in=ROLES))
        asignar_rol(usuario, self.cleaned_data["rol"])
        return usuario
