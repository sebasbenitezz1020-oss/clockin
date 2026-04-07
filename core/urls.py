from django.urls import path
from .views import (
    dashboard,

    empresas_lista,
    empresa_nueva,
    empresa_editar,
    empresa_toggle_activo,

    sucursales_lista,
    sucursal_nueva,
    sucursal_editar,
    sucursal_toggle_activo,
    obtener_sucursales_por_empresa,

    funcionarios_lista,
    funcionario_nuevo,
    funcionario_editar,
    funcionario_toggle_activo,

    turnos_lista,
    turno_nuevo,
    turno_editar,
    turno_toggle_activo,

    asistencia_marcar,

    permisos_lista,
    permiso_nuevo,
    permiso_editar,

    vacaciones_lista,
    vacacion_nueva,
    vacacion_editar,

    icl_lista,
    reportes,
    historial_lista,
)

urlpatterns = [
    path("", dashboard, name="dashboard"),

    path("empresas/", empresas_lista, name="empresas_lista"),
    path("empresas/nueva/", empresa_nueva, name="empresa_nueva"),
    path("empresas/<int:pk>/editar/", empresa_editar, name="empresa_editar"),
    path("empresas/<int:pk>/toggle-activo/", empresa_toggle_activo, name="empresa_toggle_activo"),

    path("sucursales/", sucursales_lista, name="sucursales_lista"),
    path("sucursales/nueva/", sucursal_nueva, name="sucursal_nueva"),
    path("sucursales/<int:pk>/editar/", sucursal_editar, name="sucursal_editar"),
    path("sucursales/<int:pk>/toggle-activo/", sucursal_toggle_activo, name="sucursal_toggle_activo"),
    path("ajax/sucursales-por-empresa/", obtener_sucursales_por_empresa, name="obtener_sucursales_por_empresa"),

    path("funcionarios/", funcionarios_lista, name="funcionarios_lista"),
    path("funcionarios/nuevo/", funcionario_nuevo, name="funcionario_nuevo"),
    path("funcionarios/<int:pk>/editar/", funcionario_editar, name="funcionario_editar"),
    path("funcionarios/<int:pk>/toggle-activo/", funcionario_toggle_activo, name="funcionario_toggle_activo"),

    path("turnos/", turnos_lista, name="turnos_lista"),
    path("turnos/nuevo/", turno_nuevo, name="turno_nuevo"),
    path("turnos/<int:pk>/editar/", turno_editar, name="turno_editar"),
    path("turnos/<int:pk>/toggle-activo/", turno_toggle_activo, name="turno_toggle_activo"),

    path("asistencia/", asistencia_marcar, name="asistencia_marcar"),

    path("permisos/", permisos_lista, name="permisos_lista"),
    path("permisos/nuevo/", permiso_nuevo, name="permiso_nuevo"),
    path("permisos/<int:pk>/editar/", permiso_editar, name="permiso_editar"),

    path("vacaciones/", vacaciones_lista, name="vacaciones_lista"),
    path("vacaciones/nueva/", vacacion_nueva, name="vacacion_nueva"),
    path("vacaciones/<int:pk>/editar/", vacacion_editar, name="vacacion_editar"),

    path("icl/", icl_lista, name="icl_lista"),
    path("reportes/", reportes, name="reportes"),
    path("historial/", historial_lista, name="historial_lista"),
]