from django.urls import path, include
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

    deudas_lista,
    deuda_nueva,
    deuda_editar,
    deuda_toggle_activa,

    nomina_lista,
    nomina_toggle_pagado,

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
    configuracion_general,

    liquidaciones_lista,
    liquidacion_nueva,
    liquidacion_detalle,
    liquidacion_preview,
    liquidacion_confirmar,
    liquidacion_marcar_pagada,
    liquidacion_anular,
    liquidacion_pdf,

    dias_libres_lista,
    dia_libre_nuevo,
    dia_libre_editar,
    dia_libre_toggle_activo,
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

    path("deudas/", deudas_lista, name="deudas_lista"),
    path("deudas/nueva/", deuda_nueva, name="deuda_nueva"),
    path("deudas/<int:pk>/editar/", deuda_editar, name="deuda_editar"),
    path("deudas/<int:pk>/toggle-activa/", deuda_toggle_activa, name="deuda_toggle_activa"),

    path("nomina/", nomina_lista, name="nomina_lista"),
    path("nomina/<int:pk>/toggle-pagado/", nomina_toggle_pagado, name="nomina_toggle_pagado"),

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
    path("configuracion/", configuracion_general, name="configuracion_general"),

    path("liquidaciones/", liquidaciones_lista, name="liquidaciones_lista"),
    path("liquidaciones/nueva/", liquidacion_nueva, name="liquidacion_nueva"),
    path("liquidaciones/<int:pk>/", liquidacion_detalle, name="liquidacion_detalle"),
    path("liquidaciones/preview/", liquidacion_preview, name="liquidacion_preview"),
    path("liquidaciones/<int:pk>/confirmar/", liquidacion_confirmar, name="liquidacion_confirmar"),
    path("liquidaciones/<int:pk>/pagada/", liquidacion_marcar_pagada, name="liquidacion_marcar_pagada"),
    path("liquidaciones/<int:pk>/anular/", liquidacion_anular, name="liquidacion_anular"),
    path("liquidaciones/<int:pk>/pdf/", liquidacion_pdf, name="liquidacion_pdf"),

    path("dias-libres/", dias_libres_lista, name="dias_libres_lista"),
    path("dias-libres/nuevo/", dia_libre_nuevo, name="dia_libre_nuevo"),
    path("dias-libres/<int:pk>/editar/", dia_libre_editar, name="dia_libre_editar"),
    path("dias-libres/<int:pk>/toggle-activo/", dia_libre_toggle_activo, name="dia_libre_toggle_activo"),
    path("usuarios/", include("usuarios.urls")),
]