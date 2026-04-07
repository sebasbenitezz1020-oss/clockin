from django.contrib import admin
from .models import Funcionario, Turno, Asistencia, PermisoLicencia, Vacacion, HistorialAccion


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
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
class FuncionarioAdmin(admin.ModelAdmin):
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
class AsistenciaAdmin(admin.ModelAdmin):
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
class PermisoLicenciaAdmin(admin.ModelAdmin):
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
class VacacionAdmin(admin.ModelAdmin):
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
class HistorialAccionAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "usuario", "modulo", "accion", "descripcion")
    list_filter = ("modulo", "accion", "creado_en")
    search_fields = ("descripcion", "usuario__username", "usuario__first_name", "usuario__last_name")