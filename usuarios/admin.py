from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PermisoUsuario, Usuario
from .multiempresa import es_admin_master


class MasterOnlyAdminMixin:
    def has_module_permission(self, request):
        return es_admin_master(request.user)

    def has_view_permission(self, request, obj=None):
        return es_admin_master(request.user)

    def has_add_permission(self, request):
        return es_admin_master(request.user)

    def has_change_permission(self, request, obj=None):
        return es_admin_master(request.user)

    def has_delete_permission(self, request, obj=None):
        return es_admin_master(request.user)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if es_admin_master(request.user):
            return queryset
        return queryset.none()


@admin.register(Usuario)
class UsuarioAdmin(MasterOnlyAdminMixin, UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Información adicional", {
            "fields": ("rol", "telefono", "activo")
        }),
    )

    list_display = ("username", "first_name", "last_name", "email", "rol", "activo", "is_staff")
    list_filter = ("rol", "activo", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email")


@admin.register(PermisoUsuario)
class PermisoUsuarioAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "usuario",
        "modulo",
        "puede_ver",
        "puede_crear",
        "puede_editar",
        "puede_eliminar",
        "puede_aprobar",
        "puede_confirmar",
        "puede_pagar",
        "puede_anular",
        "activo",
    )
    list_filter = ("modulo", "activo")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name")
