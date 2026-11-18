from django.urls import path

from accounts.roles import solo_admin

from . import views_tokens

app_name = "api"

urlpatterns = [
    path("tokens/", solo_admin(views_tokens.tokens), name="tokens"),
    path("tokens/<int:pk>/revocar/", solo_admin(views_tokens.revocar), name="revocar"),
]
