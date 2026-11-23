from django.urls import path
from .roles import solo_admin
from .views import (SignInView, SignOutView, perfil_add_edit, perfil_delete, perfiles, prueba, set_theme,
                    usuario_add_edit, usuarios)

app_name = "accounts"

urlpatterns = [
    path('login/', SignInView.as_view(), name='login'),
    path('logout/', SignOutView.as_view(), name='logout'),
    path('prueba/', prueba, name='prueba'),
    path("usuarios/", solo_admin(usuarios), name="usuarios"),
    path("usuarios/nuevo/", solo_admin(usuario_add_edit), name="usuario_add"),
    path("usuarios/<int:pk>/editar/", solo_admin(usuario_add_edit), name="usuario_edit"),
    path("perfiles/", solo_admin(perfiles), name="perfiles"),
    path("perfiles/nuevo/", solo_admin(perfil_add_edit), name="perfil_add"),
    path("perfiles/<int:pk>/editar/", solo_admin(perfil_add_edit), name="perfil_edit"),
    path("perfiles/<int:pk>/eliminar/", solo_admin(perfil_delete), name="perfil_delete"),
    path("set-theme/", set_theme, name="set_theme"),

]
