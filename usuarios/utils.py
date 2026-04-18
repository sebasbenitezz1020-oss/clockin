from django.contrib import messages
from django.shortcuts import redirect

from .models import PermisoUsuario


def es_admin_total(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or getattr(user, "rol", "") == "admin"


def tiene_permiso(user, modulo, accion="puede_ver"):
    if not user.is_authenticated:
        return False

    if es_admin_total(user):
        return True

    try:
        permiso = PermisoUsuario.objects.get(
            usuario=user,
            modulo=modulo,
            activo=True
        )
    except PermisoUsuario.DoesNotExist:
        return False

    return bool(getattr(permiso, accion, False))


def validar_permiso_o_redirigir(request, modulo, accion="puede_ver", destino="dashboard"):
    if tiene_permiso(request.user, modulo, accion):
        return None

    messages.error(request, "No tienes permiso para acceder a este módulo o realizar esta acción.")
    return redirect(destino)