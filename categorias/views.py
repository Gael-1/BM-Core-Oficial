from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoriaForm
from .models import Categoria


def index(request):
    return render(request, "categorias/index.html", {"categorias": Categoria.objects.order_by("nombre")})


def add_edit(request, pk=None):
    categoria = get_object_or_404(Categoria, pk=pk) if pk else None
    form = CategoriaForm(request.POST if request.method == "POST" else None, instance=categoria)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoría guardada correctamente.")
        return redirect("categorias:index")
    return render(request, "categorias/add_edit.html", {"form": form, "categoria": categoria})
