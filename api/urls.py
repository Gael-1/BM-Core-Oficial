from django.urls import path

from accounts.roles import solo_admin

from . import views_tokens, views_webhooks

app_name = "api"

urlpatterns = [
    path("tokens/", solo_admin(views_tokens.tokens), name="tokens"),
    path("tokens/<int:pk>/revocar/", solo_admin(views_tokens.revocar), name="revocar"),
    path("webhooks/", solo_admin(views_webhooks.webhooks), name="webhooks"),
    path("webhooks/<int:pk>/alternar/", solo_admin(views_webhooks.webhook_alternar), name="webhook_alternar"),
    path("webhooks/<int:pk>/eliminar/", solo_admin(views_webhooks.webhook_eliminar), name="webhook_eliminar"),
]
