from django.urls import path
from .views import (
    biometrico_inicio,
    kiosko,
    kiosko_celular,
    laboratorio_offline,
    laboratorio_offline_descriptores,
    laboratorio_offline_sw,
    registrar_rostro,
    rostros_pendientes,
    reconocimiento,
)

urlpatterns = [
    path("", biometrico_inicio, name="biometrico_inicio"),
    path("lector/", kiosko, name="biometrico_kiosko"),
    path("celular/", kiosko_celular, name="biometrico_celular"),
    path("laboratorio-offline/", laboratorio_offline, name="biometrico_laboratorio_offline"),
    path("laboratorio-offline/descriptores/", laboratorio_offline_descriptores, name="biometrico_laboratorio_descriptores"),
    path("laboratorio-offline/sw.js", laboratorio_offline_sw, name="biometrico_laboratorio_sw"),
    path("rostros-pendientes/", rostros_pendientes, name="biometrico_rostros_pendientes"),
    path("registrar/<int:funcionario_id>/", registrar_rostro, name="registrar_rostro"),
    path("reconocer/", reconocimiento, name="biometrico_reconocer"),
]
