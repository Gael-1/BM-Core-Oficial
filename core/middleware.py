# core/middleware.py
from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve

EXEMPT_URLS = [
    "accounts:login", 
    "accounts:logout",
]

# La API usa tokens en la cabecera Authorization, no sesión de navegador.
EXEMPT_NAMESPACES = ["api_v1"]


class LoginRequiredMiddleware:
    """
    Requiere login para todas las vistas, excepto las que estén en EXEMPT_URLS.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resolver_match = resolve(request.path_info)

        if not request.user.is_authenticated and resolver_match.view_name not in EXEMPT_URLS \
                and resolver_match.namespace not in EXEMPT_NAMESPACES:
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)
