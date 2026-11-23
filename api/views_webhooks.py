from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import EVENTOS, Webhook


class WebhookForm(forms.Form):
    nombre = forms.CharField(max_length=100, label="Nombre del sistema",
                             widget=forms.TextInput(attrs={"class": "form-control"}))
    url = forms.URLField(max_length=300, label="URL de destino",
                         widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}))
    eventos = forms.MultipleChoiceField(choices=EVENTOS, label="Eventos", widget=forms.CheckboxSelectMultiple)

    def clean_url(self):
        url = self.cleaned_data["url"]
        if not url.lower().startswith(("http://", "https://")):
            raise forms.ValidationError("Usa una dirección http:// o https://.")
        return url


def webhooks(request):
    form = WebhookForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        hook = Webhook.objects.create(
            nombre=form.cleaned_data["nombre"].strip(), url=form.cleaned_data["url"],
            eventos=",".join(form.cleaned_data["eventos"]),
        )
        messages.success(request, f"Webhook «{hook.nombre}» creado. Su secreto de firma está en la lista.")
        return redirect("api:webhooks")
    return render(request, "api/webhooks.html", {"form": form, "hooks": Webhook.objects.all()})


@require_POST
def webhook_alternar(request, pk):
    hook = get_object_or_404(Webhook, pk=pk)
    hook.activo = not hook.activo
    hook.save(update_fields=["activo"])
    return redirect("api:webhooks")


@require_POST
def webhook_eliminar(request, pk):
    hook = get_object_or_404(Webhook, pk=pk)
    nombre = hook.nombre
    hook.delete()
    messages.success(request, f"Webhook «{nombre}» eliminado.")
    return redirect("api:webhooks")
