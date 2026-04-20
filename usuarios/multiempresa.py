def es_admin_master(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or getattr(user, "rol", "") == "admin"


def obtener_empresa_usuario(user):
    if not user.is_authenticated:
        return None
    return getattr(user, "empresa", None)


def filtrar_por_empresa(queryset, user, campo_empresa="empresa"):
    if es_admin_master(user):
        return queryset

    empresa = obtener_empresa_usuario(user)
    if empresa is None:
        return queryset.none()

    filtro = {campo_empresa: empresa}
    return queryset.filter(**filtro)


def filtrar_por_empresa_relacion(queryset, user, campo_relacion_empresa):
    if es_admin_master(user):
        return queryset

    empresa = obtener_empresa_usuario(user)
    if empresa is None:
        return queryset.none()

    filtro = {campo_relacion_empresa: empresa}
    return queryset.filter(**filtro)