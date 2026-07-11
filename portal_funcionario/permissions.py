from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from core.models import Funcionario
from usuarios.multiempresa import es_admin_master, obtener_empresa_activa
from usuarios.utils import tiene_permiso


def usuario_es_funcionario(user):
    return getattr(user, "rol", "") == "funcionario"


def funcionario_del_usuario(user):
    funcionario = getattr(user, "funcionario", None)
    if not funcionario or not funcionario.activo:
        return None
    if not funcionario.empresa:
        return None
    if not getattr(user, "portal_activo", True):
        return None
    return funcionario


def obtener_funcionario_portal(request, funcionario_id=None):
    user = request.user

    funcionario_propio = funcionario_del_usuario(user)
    if funcionario_propio and not funcionario_id:
        return funcionario_propio, None

    if usuario_es_funcionario(user):
        if not funcionario_propio:
            return None, redirect("portal_sin_acceso")
        if funcionario_id and funcionario_propio.pk != int(funcionario_id):
            messages.error(request, "No puedes acceder al portal de otro funcionario.")
            return None, redirect("portal_dashboard")
        return funcionario_propio, None

    if funcionario_id:
        if not (es_admin_master(user) or tiene_permiso(user, "funcionarios", "puede_ver")):
            messages.error(request, "No tienes permiso para acceder al portal administrativo.")
            return None, redirect("dashboard")

        funcionario = get_object_or_404(
            Funcionario.objects.select_related("sucursal_rel", "sucursal_rel__empresa", "turno"),
            pk=funcionario_id,
            activo=True,
        )

        empresa = obtener_empresa_activa(request)
        if empresa and (not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa):
            messages.error(request, "No puedes acceder a datos de otra empresa.")
            return None, redirect("funcionarios_lista")

        return funcionario, None

    return None, redirect("dashboard")
