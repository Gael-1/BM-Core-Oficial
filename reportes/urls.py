from django.urls import path

from accounts.roles import lectura
from . import views

app_name = "reportes"

urlpatterns = [
    path('', lectura(views.inicio_reportes), name='inicio'),
]
