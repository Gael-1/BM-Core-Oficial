from django.urls import path
from .views import HomeView, kpis_parcial

app_name = "home"

urlpatterns = [
    path("", HomeView.as_view(), name="index"),
    path("kpis/", kpis_parcial, name="kpis"),
]
