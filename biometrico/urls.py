from django.urls import path
from .views import biometrico_inicio, kiosko, kiosko_celular, registrar_rostro, reconocimiento

urlpatterns = [
    path("", biometrico_inicio, name="biometrico_inicio"),
    path("lector/", kiosko, name="biometrico_kiosko"),
    path("celular/", kiosko_celular, name="biometrico_celular"),
    path("registrar/<int:funcionario_id>/", registrar_rostro, name="registrar_rostro"),
    path("reconocer/", reconocimiento, name="biometrico_reconocer"),
]
