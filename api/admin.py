from django.contrib import admin

from .models import TokenAPI


@admin.register(TokenAPI)
class TokenAPIAdmin(admin.ModelAdmin):
    list_display = ("nombre", "usuario", "inicio", "activo", "creado", "ultimo_uso")
    readonly_fields = ("inicio", "hash", "creado", "ultimo_uso")
