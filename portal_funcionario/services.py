from django.utils import timezone

from core.models import HistorialAccion


def registrar_accion_portal(request, funcionario, accion, descripcion):
    empresa = funcionario.empresa if funcionario else None
    HistorialAccion.objects.create(
        usuario=request.user if request.user.is_authenticated else None,
        empresa=empresa,
        modulo="Portal del Funcionario",
        accion=accion,
        descripcion=descripcion,
    )


def asistencia_del_dia(funcionario):
    return funcionario.asistencias.filter(fecha=timezone.localdate()).first()
