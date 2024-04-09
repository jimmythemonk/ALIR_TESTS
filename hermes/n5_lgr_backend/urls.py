from django.urls import path
from . import views

urlpatterns = [
    path("", views.backend, name="backend"),
]
