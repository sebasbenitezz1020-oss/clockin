from django.urls import path
from .views import usuarios_lista, usuario_permisos

urlpatterns = [
    path("", usuarios_lista, name="usuarios_lista"),
    path("<int:pk>/permisos/", usuario_permisos, name="usuario_permisos"),
]