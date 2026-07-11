from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import ComunicacionLaboral, DocumentoFuncionario, PermisoLicencia, Vacacion

from usuarios.multiempresa import es_admin_master, obtener_empresa_activa
from usuarios.utils import tiene_permiso

from .forms import (
    PortalGestionSolicitudDocumentoForm,
    PortalGestionSolicitudMarcacionForm,
    PortalGestionPermisoForm,
    PortalGestionVacacionForm,
    PortalDescargoComunicacionForm,
    PortalGestionSugerenciaForm,
    PortalPermisoForm,
    PortalSolicitudDocumentoForm,
    PortalSolicitudMarcacionForm,
    PortalSugerenciaForm,
    PortalVacacionForm,
)
from .models import (
    PortalComunicacionLectura,
    PortalDescargoComunicacion,
    PortalDocumentoLectura,
    PortalSolicitudDocumento,
    PortalSolicitudMarcacion,
    PortalSugerencia,
)
from .permissions import obtener_funcionario_portal
from .services import asistencia_del_dia, registrar_accion_portal


def _portal_context(request, funcionario):
    return {
        "portal_funcionario": funcionario,
        "portal_empresa": funcionario.empresa,
        "modo_admin_portal": getattr(request.user, "rol", "") != "funcionario",
    }


def _portal_asistencias_url(funcionario_id=None):
    if funcionario_id:
        return "portal_admin_asistencias", [funcionario_id]
    return "portal_asistencias", []


def _portal_documentos_url(funcionario_id=None):
    if funcionario_id:
        return "portal_admin_documentos", [funcionario_id]
    return "portal_documentos", []


def _portal_sugerencias_url(funcionario_id=None):
    if funcionario_id:
        return "portal_admin_sugerencias", [funcionario_id]
    return "portal_sugerencias", []


def _permite_descargo(comunicacion):
    return comunicacion.tipo in [
        ComunicacionLaboral.Tipos.AMONESTACION,
        ComunicacionLaboral.Tipos.CITACION_DESCARGO,
        ComunicacionLaboral.Tipos.SUSPENSION,
    ]


def _documentos_queryset(funcionario):
    return DocumentoFuncionario.objects.filter(
        funcionario=funcionario,
        activo=True,
    ).select_related("funcionario", "empresa", "sucursal").order_by("-creado_en")


def _comunicaciones_queryset(funcionario):
    return ComunicacionLaboral.objects.filter(
        funcionario=funcionario,
    ).exclude(
        estado__in=[
            ComunicacionLaboral.Estados.BORRADOR,
            ComunicacionLaboral.Estados.ANULADA,
        ]
    ).select_related("funcionario", "empresa", "sucursal", "generado_por").order_by("-fecha_emision", "-creado_en")


def _lectura_documento(funcionario, documento, usuario=None):
    return PortalDocumentoLectura.objects.get_or_create(
        funcionario=funcionario,
        documento=documento,
        defaults={
            "empresa": funcionario.empresa,
            "usuario": usuario,
        },
    )[0]


def _lectura_comunicacion(funcionario, comunicacion, usuario=None):
    return PortalComunicacionLectura.objects.get_or_create(
        funcionario=funcionario,
        comunicacion=comunicacion,
        defaults={
            "empresa": funcionario.empresa,
            "usuario": usuario,
        },
    )[0]


@login_required
def portal_sin_acceso(request):
    return render(request, "portal_funcionario/sin_acceso.html")


@login_required
def portal_dashboard(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    hoy = timezone.localdate()
    asistencia_hoy = asistencia_del_dia(funcionario)
    documentos = _documentos_queryset(funcionario)
    comunicaciones = _comunicaciones_queryset(funcionario)

    documentos_leidos = PortalDocumentoLectura.objects.filter(
        funcionario=funcionario,
        documento__in=documentos,
        leido=True,
    ).values_list("documento_id", flat=True)
    comunicaciones_confirmadas = PortalComunicacionLectura.objects.filter(
        funcionario=funcionario,
        comunicacion__in=comunicaciones,
        confirmado=True,
    ).values_list("comunicacion_id", flat=True)

    documentos_nuevos = documentos.exclude(id__in=documentos_leidos).count()
    comunicaciones_sin_confirmar = comunicaciones.exclude(id__in=comunicaciones_confirmadas).count()
    solicitudes_pendientes = (
        funcionario.permisos_licencias.filter(estado="pendiente").count()
        + funcionario.vacaciones.filter(estado="pendiente").count()
        + funcionario.portal_solicitudes_documentos.filter(estado=PortalSolicitudDocumento.Estados.SOLICITADO, activo=True).count()
        + funcionario.portal_solicitudes_marcacion.filter(estado=PortalSolicitudMarcacion.Estados.PENDIENTE, activo=True).count()
    )
    saldo_deudas = funcionario.deudas.filter(activa=True).aggregate(total=Sum("saldo_pendiente"))["total"] or 0

    context = {
        **_portal_context(request, funcionario),
        "hoy": hoy,
        "asistencia_hoy": asistencia_hoy,
        "proximo_turno": funcionario.turno,
        "vacaciones_disponibles": funcionario.saldo_vacaciones,
        "solicitudes_pendientes": solicitudes_pendientes,
        "saldo_deudas": saldo_deudas,
        "documentos_nuevos": documentos_nuevos,
        "comunicaciones_sin_confirmar": comunicaciones_sin_confirmar,
        "ultimas_comunicaciones": comunicaciones[:4],
        "ultimos_documentos": documentos[:4],
    }
    return render(request, "portal_funcionario/dashboard.html", context)


@login_required
def portal_perfil(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    return render(request, "portal_funcionario/perfil.html", _portal_context(request, funcionario))


@login_required
def portal_asistencias(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    asistencias = funcionario.asistencias.select_related("funcionario", "funcionario__turno").order_by("-fecha")[:60]
    permisos = funcionario.permisos_licencias.order_by("-fecha_desde")[:20]
    vacaciones = funcionario.vacaciones.order_by("-fecha_desde")[:20]
    solicitudes_marcacion = funcionario.portal_solicitudes_marcacion.filter(activo=True).order_by("-creado_en")[:20]

    context = {
        **_portal_context(request, funcionario),
        "asistencias": asistencias,
        "permisos": permisos,
        "vacaciones": vacaciones,
        "solicitudes_marcacion": solicitudes_marcacion,
    }
    return render(request, "portal_funcionario/asistencias.html", context)


@login_required
def portal_permiso_solicitar(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    if request.method == "POST":
        form = PortalPermisoForm(request.POST, request.FILES)
        if form.is_valid():
            permiso = form.save(commit=False)
            permiso.funcionario = funcionario
            permiso.estado = PermisoLicencia.Estados.PENDIENTE
            permiso.observacion = "Solicitud creada desde Portal del Funcionario."
            permiso.save()
            registrar_accion_portal(request, funcionario, "Solicitar permiso", f"Solicito permiso del {permiso.fecha_desde} al {permiso.fecha_hasta}.")
            messages.success(request, "Solicitud de permiso enviada correctamente.")
            url_name, args = _portal_asistencias_url(funcionario_id)
            return redirect(url_name, *args)
    else:
        form = PortalPermisoForm()

    return render(request, "portal_funcionario/solicitud_form.html", {
        **_portal_context(request, funcionario),
        "form": form,
        "titulo": "Solicitar permiso",
        "descripcion": "Tu solicitud quedará pendiente de revisión por RRHH.",
        "boton": "Enviar solicitud",
    })


@login_required
def portal_vacacion_solicitar(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    if request.method == "POST":
        form = PortalVacacionForm(request.POST, funcionario=funcionario)
        if form.is_valid():
            vacacion = form.save(commit=False)
            vacacion.funcionario = funcionario
            vacacion.estado = Vacacion.Estados.PENDIENTE
            vacacion.save()
            registrar_accion_portal(request, funcionario, "Solicitar vacaciones", f"Solicito {vacacion.dias_solicitados} día(s) desde {vacacion.fecha_desde}.")
            messages.success(request, "Solicitud de vacaciones enviada correctamente.")
            url_name, args = _portal_asistencias_url(funcionario_id)
            return redirect(url_name, *args)
    else:
        form = PortalVacacionForm(funcionario=funcionario)

    return render(request, "portal_funcionario/solicitud_form.html", {
        **_portal_context(request, funcionario),
        "form": form,
        "titulo": "Solicitar vacaciones",
        "descripcion": f"Saldo disponible: {funcionario.saldo_vacaciones} día(s).",
        "boton": "Enviar solicitud",
    })


@login_required
def portal_marcacion_solicitar(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    if request.method == "POST":
        form = PortalSolicitudMarcacionForm(request.POST, request.FILES)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.funcionario = funcionario
            solicitud.empresa = funcionario.empresa
            solicitud.solicitado_por = request.user
            solicitud.asistencia = funcionario.asistencias.filter(fecha=solicitud.fecha).first()
            solicitud.save()
            registrar_accion_portal(request, funcionario, "Solicitar corrección de marcación", f"Solicito corrección para {solicitud.fecha}.")
            messages.success(request, "Solicitud de corrección enviada correctamente.")
            url_name, args = _portal_asistencias_url(funcionario_id)
            return redirect(url_name, *args)
    else:
        form = PortalSolicitudMarcacionForm()

    return render(request, "portal_funcionario/solicitud_form.html", {
        **_portal_context(request, funcionario),
        "form": form,
        "titulo": "Solicitar corrección de marcación",
        "descripcion": "Esta solicitud no modifica la asistencia. RRHH revisará el caso.",
        "boton": "Enviar solicitud",
    })


@login_required
def portal_deudas(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    deudas = funcionario.deudas.order_by("-fecha", "-creado_en")
    context = {
        **_portal_context(request, funcionario),
        "deudas": deudas,
        "saldo_total": deudas.filter(activa=True).aggregate(total=Sum("saldo_pendiente"))["total"] or 0,
    }
    return render(request, "portal_funcionario/deudas.html", context)


@login_required
def portal_documentos(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    documentos = _documentos_queryset(funcionario)
    lecturas = {
        item.documento_id: item
        for item in PortalDocumentoLectura.objects.filter(funcionario=funcionario, documento__in=documentos)
    }
    filas = []
    for documento in documentos:
        lectura = lecturas.get(documento.id)
        filas.append({
            "documento": documento,
            "lectura": lectura,
            "leido": bool(lectura and lectura.leido),
            "confirmado": bool(lectura and lectura.confirmado),
        })

    solicitudes = PortalSolicitudDocumento.objects.filter(funcionario=funcionario, activo=True).order_by("-creado_en")[:20]

    context = {
        **_portal_context(request, funcionario),
        "documentos": filas,
        "solicitudes_documentos": solicitudes,
    }
    return render(request, "portal_funcionario/documentos.html", context)


@login_required
def portal_documento_solicitar(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    if request.method == "POST":
        form = PortalSolicitudDocumentoForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.funcionario = funcionario
            solicitud.empresa = funcionario.empresa
            solicitud.solicitado_por = request.user
            solicitud.save()
            registrar_accion_portal(request, funcionario, "Solicitar documento", f"Solicito {solicitud.get_tipo_display()}.")
            messages.success(request, "Solicitud documental enviada correctamente.")
            url_name, args = _portal_documentos_url(funcionario_id)
            return redirect(url_name, *args)
    else:
        form = PortalSolicitudDocumentoForm()

    return render(request, "portal_funcionario/solicitud_form.html", {
        **_portal_context(request, funcionario),
        "form": form,
        "titulo": "Solicitar documento",
        "descripcion": "RRHH preparará el documento y lo adjuntará cuando esté listo.",
        "boton": "Enviar solicitud",
    })


@login_required
def portal_notificaciones(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    documentos = _documentos_queryset(funcionario)
    comunicaciones = _comunicaciones_queryset(funcionario)
    documentos_confirmados = PortalDocumentoLectura.objects.filter(
        funcionario=funcionario,
        documento__in=documentos,
        confirmado=True,
    ).values_list("documento_id", flat=True)
    comunicaciones_confirmadas = PortalComunicacionLectura.objects.filter(
        funcionario=funcionario,
        comunicacion__in=comunicaciones,
        confirmado=True,
    ).values_list("comunicacion_id", flat=True)

    notificaciones = []
    for documento in documentos.exclude(id__in=documentos_confirmados)[:10]:
        notificaciones.append({
            "tipo": "Documento",
            "titulo": documento.titulo,
            "detalle": documento.get_tipo_display(),
            "fecha": documento.creado_en,
            "url_name": "portal_admin_documentos" if funcionario_id else "portal_documentos",
            "args": [funcionario_id] if funcionario_id else [],
        })
    for comunicacion in comunicaciones.exclude(id__in=comunicaciones_confirmadas)[:10]:
        notificaciones.append({
            "tipo": "Comunicación",
            "titulo": comunicacion.titulo,
            "detalle": comunicacion.get_tipo_display(),
            "fecha": comunicacion.creado_en,
            "url_name": "portal_admin_comunicacion_detalle" if funcionario_id else "portal_comunicacion_detalle",
            "args": [funcionario_id, comunicacion.id] if funcionario_id else [comunicacion.id],
        })
    for solicitud in funcionario.portal_solicitudes_documentos.filter(activo=True).exclude(estado=PortalSolicitudDocumento.Estados.CANCELADO)[:10]:
        notificaciones.append({
            "tipo": "Solicitud documental",
            "titulo": solicitud.get_tipo_display(),
            "detalle": solicitud.get_estado_display(),
            "fecha": solicitud.actualizado_en,
            "url_name": "portal_admin_documentos" if funcionario_id else "portal_documentos",
            "args": [funcionario_id] if funcionario_id else [],
        })
    for sugerencia in funcionario.portal_sugerencias.filter(activo=True).exclude(respuesta_operador="")[:10]:
        notificaciones.append({
            "tipo": "Sugerencia",
            "titulo": sugerencia.asunto,
            "detalle": sugerencia.get_estado_display(),
            "fecha": sugerencia.actualizado_en,
            "url_name": "portal_admin_sugerencias" if funcionario_id else "portal_sugerencias",
            "args": [funcionario_id] if funcionario_id else [],
        })

    notificaciones.sort(key=lambda item: item["fecha"], reverse=True)
    return render(request, "portal_funcionario/notificaciones.html", {
        **_portal_context(request, funcionario),
        "notificaciones": notificaciones[:30],
    })


@login_required
def portal_sugerencias(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    sugerencias = funcionario.portal_sugerencias.filter(activo=True).order_by("-creado_en")[:40]
    return render(request, "portal_funcionario/sugerencias.html", {
        **_portal_context(request, funcionario),
        "sugerencias": sugerencias,
    })


@login_required
def portal_sugerencia_crear(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    if request.method == "POST":
        form = PortalSugerenciaForm(request.POST, request.FILES)
        if form.is_valid():
            sugerencia = form.save(commit=False)
            sugerencia.funcionario = funcionario
            sugerencia.empresa = funcionario.empresa
            sugerencia.enviado_por = request.user
            sugerencia.save()
            registrar_accion_portal(request, funcionario, "Enviar sugerencia", f"Sugerencia enviada: {sugerencia.asunto}.")
            messages.success(request, "Sugerencia enviada correctamente.")
            url_name, args = _portal_sugerencias_url(funcionario_id)
            return redirect(url_name, *args)
    else:
        form = PortalSugerenciaForm()

    return render(request, "portal_funcionario/solicitud_form.html", {
        **_portal_context(request, funcionario),
        "form": form,
        "titulo": "Enviar sugerencia",
        "descripcion": "Tu sugerencia quedará registrada para revisión interna.",
        "boton": "Enviar sugerencia",
    })


@login_required
def portal_documento_confirmar(request, pk, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    documento = get_object_or_404(_documentos_queryset(funcionario), pk=pk)
    lectura = _lectura_documento(funcionario, documento, request.user)

    if request.method == "POST":
        lectura.confirmar(request.user)
        registrar_accion_portal(request, funcionario, "Confirmar documento", f"Confirmó recepción del documento {documento.titulo}.")
        messages.success(request, "Documento confirmado correctamente.")
    else:
        lectura.marcar_leido(request.user)

    url_name, args = _portal_documentos_url(funcionario_id)
    return redirect(url_name, *args)


@login_required
def portal_comunicaciones(request, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    comunicaciones = _comunicaciones_queryset(funcionario)
    lecturas = {
        item.comunicacion_id: item
        for item in PortalComunicacionLectura.objects.filter(funcionario=funcionario, comunicacion__in=comunicaciones)
    }
    filas = []
    for comunicacion in comunicaciones:
        lectura = lecturas.get(comunicacion.id)
        filas.append({
            "comunicacion": comunicacion,
            "lectura": lectura,
            "abierto": bool(lectura and lectura.abierto),
            "confirmado": bool(lectura and lectura.confirmado),
        })

    context = {
        **_portal_context(request, funcionario),
        "comunicaciones": filas,
    }
    return render(request, "portal_funcionario/comunicaciones.html", context)


@login_required
def portal_comunicacion_detalle(request, pk, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    comunicacion = get_object_or_404(_comunicaciones_queryset(funcionario), pk=pk)
    lectura = _lectura_comunicacion(funcionario, comunicacion, request.user)
    lectura.marcar_abierto(request.user)

    context = {
        **_portal_context(request, funcionario),
        "comunicacion": comunicacion,
        "lectura": lectura,
        "descargos": comunicacion.portal_descargos.filter(funcionario=funcionario, activo=True),
        "puede_enviar_descargo": _permite_descargo(comunicacion),
        "descargo_form": PortalDescargoComunicacionForm(),
    }
    return render(request, "portal_funcionario/comunicacion_detalle.html", context)


@login_required
def portal_descargo_enviar(request, pk, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    comunicacion = get_object_or_404(_comunicaciones_queryset(funcionario), pk=pk)
    if not _permite_descargo(comunicacion):
        messages.error(request, "Esta comunicación no admite descargo desde el portal.")
        if funcionario_id:
            return redirect("portal_admin_comunicacion_detalle", funcionario_id=funcionario_id, pk=comunicacion.pk)
        return redirect("portal_comunicacion_detalle", pk=comunicacion.pk)

    if request.method == "POST":
        form = PortalDescargoComunicacionForm(request.POST, request.FILES)
        if form.is_valid():
            descargo = form.save(commit=False)
            descargo.comunicacion = comunicacion
            descargo.funcionario = funcionario
            descargo.empresa = funcionario.empresa
            descargo.enviado_por = request.user
            descargo.save()
            registrar_accion_portal(request, funcionario, "Enviar descargo", f"Descargo enviado para {comunicacion.titulo}.")
            messages.success(request, "Descargo enviado correctamente.")

    if funcionario_id:
        return redirect("portal_admin_comunicacion_detalle", funcionario_id=funcionario_id, pk=comunicacion.pk)
    return redirect("portal_comunicacion_detalle", pk=comunicacion.pk)


@login_required
def portal_comunicacion_confirmar(request, pk, funcionario_id=None):
    funcionario, respuesta = obtener_funcionario_portal(request, funcionario_id)
    if respuesta:
        return respuesta

    comunicacion = get_object_or_404(_comunicaciones_queryset(funcionario), pk=pk)
    lectura = _lectura_comunicacion(funcionario, comunicacion, request.user)

    if request.method == "POST":
        lectura.confirmar(request.user)
        registrar_accion_portal(request, funcionario, "Confirmar comunicación", f"Confirmó recepción de {comunicacion.titulo}.")
        messages.success(request, "Recepción confirmada correctamente.")

    if funcionario_id:
        return redirect("portal_admin_comunicacion_detalle", funcionario_id=funcionario_id, pk=comunicacion.pk)
    return redirect("portal_comunicacion_detalle", pk=comunicacion.pk)


def _puede_gestionar_portal(user):
    return es_admin_master(user) or tiene_permiso(user, "portal_funcionario", "puede_ver") or tiene_permiso(user, "funcionarios", "puede_ver")


def _filtrar_empresa_portal(request, queryset):
    empresa = obtener_empresa_activa(request)
    if empresa:
        return queryset.filter(empresa=empresa)
    if es_admin_master(request.user):
        return queryset
    return queryset.none()


@login_required
def portal_bandeja(request):
    if not _puede_gestionar_portal(request.user):
        messages.error(request, "No tienes permiso para gestionar solicitudes del portal.")
        return redirect("dashboard")

    solicitudes_documentos = _filtrar_empresa_portal(
        request,
        PortalSolicitudDocumento.objects.select_related("funcionario", "empresa", "solicitado_por").filter(activo=True),
    ).order_by("-creado_en")
    solicitudes_marcacion = _filtrar_empresa_portal(
        request,
        PortalSolicitudMarcacion.objects.select_related("funcionario", "empresa", "solicitado_por").filter(activo=True),
    ).order_by("-creado_en")
    permisos = _filtrar_empresa_portal(
        request,
        PermisoLicencia.objects.select_related("funcionario", "empresa").filter(estado=PermisoLicencia.Estados.PENDIENTE),
    ).order_by("-creado_en")
    vacaciones = _filtrar_empresa_portal(
        request,
        Vacacion.objects.select_related("funcionario", "empresa").filter(estado=Vacacion.Estados.PENDIENTE),
    ).order_by("-creado_en")
    sugerencias = _filtrar_empresa_portal(
        request,
        PortalSugerencia.objects.select_related("funcionario", "empresa", "enviado_por").filter(activo=True),
    ).order_by("-creado_en")

    return render(request, "portal_funcionario/bandeja.html", {
        "portal_empresa": obtener_empresa_activa(request),
        "portal_funcionario": None,
        "modo_admin_portal": True,
        "permisos": permisos[:80],
        "vacaciones": vacaciones[:80],
        "sugerencias": sugerencias[:80],
        "solicitudes_documentos": solicitudes_documentos[:80],
        "solicitudes_marcacion": solicitudes_marcacion[:80],
    })


@login_required
def portal_permiso_gestionar(request, pk):
    if not _puede_gestionar_portal(request.user):
        messages.error(request, "No tienes permiso para gestionar solicitudes del portal.")
        return redirect("dashboard")

    permiso = get_object_or_404(_filtrar_empresa_portal(request, PermisoLicencia.objects.select_related("funcionario", "empresa")), pk=pk)

    if request.method == "POST":
        form = PortalGestionPermisoForm(request.POST, instance=permiso)
        if form.is_valid():
            permiso = form.save()
            registrar_accion_portal(request, permiso.funcionario, "Gestionar permiso", f"Permiso {permiso.id} actualizado a {permiso.get_estado_display()}.")
            messages.success(request, "Permiso actualizado.")
            return redirect("portal_bandeja")
    else:
        form = PortalGestionPermisoForm(instance=permiso)

    return render(request, "portal_funcionario/gestion_form.html", {
        "form": form,
        "titulo": "Gestionar permiso",
        "solicitud": permiso,
    })


@login_required
def portal_vacacion_gestionar(request, pk):
    if not _puede_gestionar_portal(request.user):
        messages.error(request, "No tienes permiso para gestionar solicitudes del portal.")
        return redirect("dashboard")

    vacacion = get_object_or_404(_filtrar_empresa_portal(request, Vacacion.objects.select_related("funcionario", "empresa")), pk=pk)

    if request.method == "POST":
        form = PortalGestionVacacionForm(request.POST, instance=vacacion)
        if form.is_valid():
            vacacion = form.save()
            registrar_accion_portal(request, vacacion.funcionario, "Gestionar vacaciones", f"Vacación {vacacion.id} actualizada a {vacacion.get_estado_display()}.")
            messages.success(request, "Vacación actualizada.")
            return redirect("portal_bandeja")
    else:
        form = PortalGestionVacacionForm(instance=vacacion)

    return render(request, "portal_funcionario/gestion_form.html", {
        "form": form,
        "titulo": "Gestionar vacaciones",
        "solicitud": vacacion,
    })


@login_required
def portal_sugerencia_gestionar(request, pk):
    if not _puede_gestionar_portal(request.user):
        messages.error(request, "No tienes permiso para gestionar solicitudes del portal.")
        return redirect("dashboard")

    sugerencia = get_object_or_404(_filtrar_empresa_portal(request, PortalSugerencia.objects.select_related("funcionario", "empresa")), pk=pk, activo=True)

    if request.method == "POST":
        form = PortalGestionSugerenciaForm(request.POST, instance=sugerencia)
        if form.is_valid():
            sugerencia = form.save(commit=False)
            sugerencia.revisado_por = request.user
            sugerencia.revisado_en = timezone.now()
            sugerencia.save()
            registrar_accion_portal(request, sugerencia.funcionario, "Gestionar sugerencia", f"Sugerencia {sugerencia.id} actualizada a {sugerencia.get_estado_display()}.")
            messages.success(request, "Sugerencia actualizada.")
            return redirect("portal_bandeja")
    else:
        form = PortalGestionSugerenciaForm(instance=sugerencia)

    return render(request, "portal_funcionario/gestion_form.html", {
        "form": form,
        "titulo": "Gestionar sugerencia",
        "solicitud": sugerencia,
    })


@login_required
def portal_solicitud_documento_gestionar(request, pk):
    if not _puede_gestionar_portal(request.user):
        messages.error(request, "No tienes permiso para gestionar solicitudes del portal.")
        return redirect("dashboard")

    solicitud = get_object_or_404(_filtrar_empresa_portal(request, PortalSolicitudDocumento.objects.select_related("funcionario", "empresa")), pk=pk, activo=True)

    if request.method == "POST":
        form = PortalGestionSolicitudDocumentoForm(request.POST, request.FILES, instance=solicitud)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.revisado_por = request.user
            solicitud.revisado_en = timezone.now()
            solicitud.save()
            registrar_accion_portal(request, solicitud.funcionario, "Gestionar solicitud documental", f"Solicitud {solicitud.id} actualizada a {solicitud.get_estado_display()}.")
            messages.success(request, "Solicitud documental actualizada.")
            return redirect("portal_bandeja")
    else:
        form = PortalGestionSolicitudDocumentoForm(instance=solicitud)

    return render(request, "portal_funcionario/gestion_form.html", {
        "form": form,
        "titulo": "Gestionar solicitud documental",
        "solicitud": solicitud,
    })


@login_required
def portal_solicitud_marcacion_gestionar(request, pk):
    if not _puede_gestionar_portal(request.user):
        messages.error(request, "No tienes permiso para gestionar solicitudes del portal.")
        return redirect("dashboard")

    solicitud = get_object_or_404(_filtrar_empresa_portal(request, PortalSolicitudMarcacion.objects.select_related("funcionario", "empresa")), pk=pk, activo=True)

    if request.method == "POST":
        form = PortalGestionSolicitudMarcacionForm(request.POST, instance=solicitud)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.revisado_por = request.user
            solicitud.revisado_en = timezone.now()
            solicitud.save()
            registrar_accion_portal(request, solicitud.funcionario, "Gestionar solicitud de marcación", f"Solicitud {solicitud.id} actualizada a {solicitud.get_estado_display()}.")
            messages.success(request, "Solicitud de marcación actualizada.")
            return redirect("portal_bandeja")
    else:
        form = PortalGestionSolicitudMarcacionForm(instance=solicitud)

    return render(request, "portal_funcionario/gestion_form.html", {
        "form": form,
        "titulo": "Gestionar solicitud de marcación",
        "solicitud": solicitud,
    })
