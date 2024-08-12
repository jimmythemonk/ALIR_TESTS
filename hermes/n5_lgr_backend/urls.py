from django.urls import path
from . import views

urlpatterns = [
    # path("", views.backend, name="backend"),
    path("", views.maintenance, name="maintenance"),
]
