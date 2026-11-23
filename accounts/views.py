# accounts/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from accounts.models import PerfilAcceso, UserProfile
from .forms import LoginForm, PerfilAccesoForm, UsuarioForm
from .roles import rol_de
from django.contrib.auth.decorators import login_required


class SignInView(LoginView):
    form_class = LoginForm
    template_name = 'login.html'

    def form_valid(self, form):
        # Manejar "Recuérdame": si NO lo marca, hacer la sesión expirar al cerrar el navegador
        remember = form.cleaned_data.get('remember_me')
        if not remember:
            self.request.session.set_expiry(0)  # expira al cerrar navegador
        return super().form_valid(form)

class SignOutView(LogoutView):
    next_page = reverse_lazy('accounts:login')

def prueba(request): 
    template = 'prueba.html'
    return render(request, template)


def set_theme(request):
    if request.method == "POST":
        theme = request.POST.get("theme")
        if theme in ["light", "dark"]:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.theme_preference = theme
            profile.save()
            return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=400)


def usuarios(request):
    lista = [{"usuario": u, "rol": rol_de(u) or ("Superusuario" if u.is_superuser else "Sin rol")}
             for u in get_user_model().objects.order_by("username").prefetch_related("groups")]
    return render(request, "accounts/usuarios.html", {"usuarios": lista})


def usuario_add_edit(request, pk=None):
    usuario = get_object_or_404(get_user_model(), pk=pk) if pk else None
    form = UsuarioForm(request.POST if request.method == "POST" else None, instance=usuario, editor=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuario guardado correctamente.")
        return redirect("accounts:usuarios")
    return render(request, "accounts/usuario_form.html", {"form": form, "usuario": usuario})


def perfiles(request):
    lista = []
    for perfil in PerfilAcceso.objects.select_related("grupo"):
        lista.append({"perfil": perfil, "usuarios": perfil.grupo.user_set.count(),
                      "modulos": [n for n, activo in (("Inventario", perfil.inventario), ("Compras", perfil.compras),
                                                      ("Ventas", perfil.ventas), ("Administración", perfil.administrar)) if activo]})
    return render(request, "accounts/perfiles.html", {"perfiles": lista})


def perfil_add_edit(request, pk=None):
    perfil = get_object_or_404(PerfilAcceso.objects.select_related("grupo"), pk=pk) if pk else None
    form = PerfilAccesoForm(request.POST if request.method == "POST" else None, perfil=perfil)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil guardado correctamente.")
        return redirect("accounts:perfiles")
    return render(request, "accounts/perfil_form.html", {"form": form, "perfil": perfil})


def perfil_delete(request, pk):
    perfil = get_object_or_404(PerfilAcceso.objects.select_related("grupo"), pk=pk)
    if request.method == "POST":
        if perfil.grupo.user_set.exists():
            messages.error(request, "No se puede eliminar: hay usuarios con este perfil. Cámbiales el rol primero.")
        else:
            perfil.grupo.delete()
            messages.success(request, "Perfil eliminado.")
    return redirect("accounts:perfiles")
