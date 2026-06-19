from django.contrib import admin
from .models import Funcionario, Turno, Asistencia, PermisoLicencia, Vacacion, HistorialAccion
from usuarios.multiempresa import es_admin_master


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


@admin.register(Turno)
class TurnoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "nombre",
        "hora_entrada",
        "hora_salida",
        "usa_almuerzo",
        "tolerancia_minutos",
        "activo",
    )
    list_filter = ("activo", "usa_almuerzo")
    search_fields = ("nombre",)


@admin.register(Funcionario)
class FuncionarioAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "cedula",
        "apellido",
        "nombre",
        "turno",
        "cargo",
        "sector",
        "sucursal",
        "ips",
        "salario_base",
        "bono",
        "activo",
    )
    list_filter = ("activo", "ips", "turno", "sector", "sucursal")
    search_fields = ("cedula", "nombre", "apellido", "cargo", "sector", "sucursal")


@admin.register(Asistencia)
class AsistenciaAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "fecha",
        "funcionario",
        "hora_entrada",
        "hora_salida",
        "llego_tarde",
        "minutos_atraso",
    )
    list_filter = ("fecha", "llego_tarde")
    search_fields = (
        "funcionario__nombre",
        "funcionario__apellido",
        "funcionario__cedula",
    )


@admin.register(PermisoLicencia)
class PermisoLicenciaAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "funcionario",
        "tipo",
        "fecha_desde",
        "fecha_hasta",
        "estado",
        "creado_en",
    )
    list_filter = ("tipo", "estado", "fecha_desde")
    search_fields = (
        "funcionario__nombre",
        "funcionario__apellido",
        "funcionario__cedula",
        "motivo",
        "observacion",
    )


@admin.register(Vacacion)
class VacacionAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "funcionario",
        "fecha_desde",
        "fecha_hasta",
        "dias_solicitados",
        "estado",
        "creado_en",
    )
    list_filter = ("estado", "fecha_desde")
    search_fields = (
        "funcionario__nombre",
        "funcionario__apellido",
        "funcionario__cedula",
        "observacion",
    )


@admin.register(HistorialAccion)
class HistorialAccionAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("creado_en", "usuario", "empresa", "modulo", "accion", "descripcion")
    list_filter = ("empresa", "modulo", "accion", "creado_en")
    search_fields = (
        "descripcion",
        "empresa__nombre",
        "empresa__nombre_comercial",
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
    )
