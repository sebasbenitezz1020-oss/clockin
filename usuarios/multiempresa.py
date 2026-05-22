from django.shortcuts import redirect
from django.contrib import messages


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


def filtrar_empresa_directa(queryset, user):
    if es_admin_master(user):
        return queryset

    empresa = obtener_empresa_usuario(user)
    if not empresa:
        return queryset.none()

    return queryset.filter(empresa=empresa)


def filtrar_empresa_funcionario(queryset, user):
    if es_admin_master(user):
        return queryset

    empresa = obtener_empresa_usuario(user)
    if not empresa:
        return queryset.none()

    return queryset.filter(funcionario__sucursal_rel__empresa=empresa)


def validar_objeto_empresa_funcionario(request, obj, mensaje=None, redirect_to="dashboard"):
    if es_admin_master(request.user):
        return None

    empresa = obtener_empresa_usuario(request.user)
    funcionario = getattr(obj, "funcionario", None)

    if not empresa or not funcionario or not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa:
        messages.error(request, mensaje or "No puedes acceder a datos de otra empresa.")
        return redirect(redirect_to)

    return None


def validar_objeto_empresa_directa(request, obj, mensaje=None, redirect_to="dashboard"):
    if es_admin_master(request.user):
        return None

    empresa = obtener_empresa_usuario(request.user)

    if not empresa or getattr(obj, "empresa", None) != empresa:
        messages.error(request, mensaje or "No puedes acceder a datos de otra empresa.")
        return redirect(redirect_to)

    return None