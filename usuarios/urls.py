from django.urls import path
from .views import (
    usuarios_lista,
    usuario_nuevo,
    usuario_editar,
    usuario_toggle_activo,
    usuario_permisos,
)

urlpatterns = [
    path("", usuarios_lista, name="usuarios_lista"),
    path("nuevo/", usuario_nuevo, name="usuario_nuevo"),
    path("<int:pk>/editar/", usuario_editar, name="usuario_editar"),
    path("<int:pk>/toggle-activo/", usuario_toggle_activo, name="usuario_toggle_activo"),
    path("<int:pk>/permisos/", usuario_permisos, name="usuario_permisos"),
]