from django.contrib import admin

from .models import (
    PortalComunicacionLectura,
    PortalDescargoComunicacion,
    PortalDocumentoLectura,
    PortalSolicitudDocumento,
    PortalSolicitudMarcacion,
    PortalSugerencia,
)


@admin.register(PortalDocumentoLectura)
class PortalDocumentoLecturaAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "documento", "empresa", "leido", "confirmado", "actualizado_en")
    list_filter = ("leido", "confirmado", "empresa")
    search_fields = ("funcionario__nombre", "funcionario__apellido", "funcionario__cedula", "documento__titulo")


@admin.register(PortalComunicacionLectura)
class PortalComunicacionLecturaAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "comunicacion", "empresa", "abierto", "confirmado", "actualizado_en")
    list_filter = ("abierto", "confirmado", "empresa")
    search_fields = ("funcionario__nombre", "funcionario__apellido", "funcionario__cedula", "comunicacion__titulo")


@admin.register(PortalSolicitudDocumento)
class PortalSolicitudDocumentoAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "empresa", "tipo", "estado", "creado_en", "revisado_en")
    list_filter = ("estado", "tipo", "empresa")
    search_fields = ("funcionario__nombre", "funcionario__apellido", "funcionario__cedula", "motivo")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(PortalSolicitudMarcacion)
class PortalSolicitudMarcacionAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "empresa", "fecha", "tipo", "estado", "creado_en", "revisado_en")
    list_filter = ("estado", "tipo", "empresa")
    search_fields = ("funcionario__nombre", "funcionario__apellido", "funcionario__cedula", "motivo")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(PortalSugerencia)
class PortalSugerenciaAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "empresa", "categoria", "asunto", "estado", "creado_en")
    list_filter = ("estado", "categoria", "empresa")
    search_fields = ("funcionario__nombre", "funcionario__apellido", "funcionario__cedula", "asunto", "mensaje")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(PortalDescargoComunicacion)
class PortalDescargoComunicacionAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "empresa", "comunicacion", "estado", "creado_en")
    list_filter = ("estado", "empresa")
    search_fields = ("funcionario__nombre", "funcionario__apellido", "funcionario__cedula", "mensaje", "comunicacion__titulo")
    readonly_fields = ("creado_en", "actualizado_en")
