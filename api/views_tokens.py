from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import TokenAPI


class TokenForm(forms.Form):
    nombre = forms.CharField(
        max_length=100, label="Nombre del sistema",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. Punto de venta sucursal norte"}),
    )
    usuario = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(), label="Actuar como el usuario",
        help_text="El token tendrá los permisos del rol de este usuario.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")


def tokens(request):
    form = TokenForm(request.POST if request.method == "POST" else None)
    token_nuevo = None
    if request.method == "POST" and form.is_valid():
        _, token_nuevo = TokenAPI.crear(form.cleaned_data["usuario"], form.cleaned_data["nombre"].strip())
        form = TokenForm()
    # El token en claro solo se muestra en esta respuesta (no se redirige ni se guarda).
    return render(request, "api/tokens.html", {
        "form": form, "token_nuevo": token_nuevo,
        "tokens": TokenAPI.objects.select_related("usuario"),
    })


@require_POST
def revocar(request, pk):
    token = get_object_or_404(TokenAPI, pk=pk)
    token.activo = False
    token.save(update_fields=["activo"])
    messages.success(request, f"Token «{token.nombre}» revocado.")
    return redirect("api:tokens")
