from .utils import tiene_permiso, es_admin_total
from usuarios.multiempresa import es_admin_master, obtener_empresa_usuario


def multiempresa_context(request):
    if not request.user.is_authenticated:
        return {
            "empresa_usuario": None,
            "es_admin_master": False,
        }

    return {
        "empresa_usuario": obtener_empresa_usuario(request.user),
        "es_admin_master": es_admin_master(request.user),
    }


def permisos_menu(request):
    user = request.user

    if not user.is_authenticated:
        return {
            "puede_ver_dashboard": False,
            "puede_ver_empresas": False,
            "puede_ver_sucursales": False,
            "puede_ver_funcionarios": False,
            "puede_ver_turnos": False,
            "puede_ver_asistencia": False,
            "puede_ver_dias_libres": False,
            "puede_ver_deudas": False,
            "puede_ver_nomina": False,
            "puede_ver_biometrico": False,
            "puede_ver_permisos": False,
            "puede_ver_vacaciones": False,
            "puede_ver_icl": False,
            "puede_ver_reportes": False,
            "puede_ver_historial": False,
            "puede_ver_liquidacion": False,
            "puede_ver_configuracion": False,
            "puede_ver_usuarios_permisos": False,
            "es_admin_total": False,
        }

    admin_total = es_admin_total(user)

    return {
        "puede_ver_dashboard": tiene_permiso(user, "dashboard", "puede_ver"),
        "puede_ver_empresas": tiene_permiso(user, "empresas", "puede_ver"),
        "puede_ver_sucursales": tiene_permiso(user, "sucursales", "puede_ver"),
        "puede_ver_funcionarios": tiene_permiso(user, "funcionarios", "puede_ver"),
        "puede_ver_turnos": tiene_permiso(user, "turnos", "puede_ver"),
        "puede_ver_asistencia": tiene_permiso(user, "asistencia", "puede_ver"),
        "puede_ver_dias_libres": tiene_permiso(user, "dias_libres", "puede_ver"),
        "puede_ver_deudas": tiene_permiso(user, "deudas", "puede_ver"),
        "puede_ver_nomina": tiene_permiso(user, "nomina", "puede_ver"),
        "puede_ver_biometrico": tiene_permiso(user, "biometrico", "puede_ver"),
        "puede_ver_permisos": tiene_permiso(user, "permisos", "puede_ver"),
        "puede_ver_vacaciones": tiene_permiso(user, "vacaciones", "puede_ver"),
        "puede_ver_icl": tiene_permiso(user, "icl", "puede_ver"),
        "puede_ver_reportes": tiene_permiso(user, "reportes", "puede_ver"),
        "puede_ver_historial": tiene_permiso(user, "historial", "puede_ver"),
        "puede_ver_liquidacion": tiene_permiso(user, "liquidacion", "puede_ver"),
        "puede_ver_configuracion": tiene_permiso(user, "configuracion", "puede_ver"),
        "puede_ver_usuarios_permisos": admin_total,
        "es_admin_total": admin_total,
    }