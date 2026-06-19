from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def es_admin_master(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "rol", "") == "admin"
            and getattr(user, "empresa_id", None) is None
        )
    )


def obtener_empresa_usuario(user):
    if not user.is_authenticated:
        return None
    return getattr(user, "empresa", None)


def obtener_empresa_activa(request):
    if not request.user.is_authenticated:
        return None

    if es_admin_master(request.user):
        empresa_id = request.session.get("empresa_activa_id")
        if not empresa_id:
            return None

        try:
            from core.models import Empresa

            return Empresa.objects.get(pk=empresa_id)
        except Exception:
            request.session.pop("empresa_activa_id", None)
            return None

    return obtener_empresa_usuario(request.user)


def requiere_empresa_activa(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if es_admin_master(request.user) and not obtener_empresa_activa(request):
            return redirect("panel_global_empresas")
        return view_func(request, *args, **kwargs)

    return wrapper


def filtrar_empresa_directa(queryset, user, empresa=None):
    if es_admin_master(user) and empresa is None:
        return queryset

    empresa = empresa or obtener_empresa_usuario(user)
    if not empresa:
        return queryset.none()

    return queryset.filter(empresa=empresa)


def filtrar_empresa_funcionario(queryset, user, empresa=None):
    if es_admin_master(user) and empresa is None:
        return queryset

    empresa = empresa or obtener_empresa_usuario(user)
    if not empresa:
        return queryset.none()

    return queryset.filter(funcionario__sucursal_rel__empresa=empresa)


def validar_objeto_empresa_funcionario(request, obj, mensaje=None, redirect_to="dashboard"):
    empresa = obtener_empresa_activa(request)

    if es_admin_master(request.user) and not empresa:
        return None

    funcionario = getattr(obj, "funcionario", None)

    if not empresa or not funcionario or not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa:
        messages.error(request, mensaje or "No puedes acceder a datos de otra empresa.")
        return redirect(redirect_to)

    return None


def validar_objeto_empresa_directa(request, obj, mensaje=None, redirect_to="dashboard"):
    empresa = obtener_empresa_activa(request)

    if es_admin_master(request.user) and not empresa:
        return None

    if not empresa or getattr(obj, "empresa", None) != empresa:
        messages.error(request, mensaje or "No puedes acceder a datos de otra empresa.")
        return redirect(redirect_to)

    return None
