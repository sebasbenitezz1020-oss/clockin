from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from usuarios.utils import validar_permiso_o_redirigir, tiene_permiso
from usuarios.multiempresa import es_admin_master, obtener_empresa_usuario, filtrar_por_empresa_relacion
from usuarios.multiempresa import es_admin_master, obtener_empresa_usuario

from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import MarcacionManualForm
from .models import Asistencia

from .forms import (
    ConfiguracionGeneralForm,
    DeudaForm,
    DiaLibreForm,
    EmpresaForm,
    FuncionarioForm,
    LiquidacionForm,
    MarcacionForm,
    PermisoLicenciaForm,
    SucursalForm,
    TurnoForm,
    VacacionForm,
)
from .liquidacion_utils import calcular_liquidacion_funcionario
from .models import (
    Asistencia,
    ConfiguracionGeneral,
    Deuda,
    DiaLibre,
    Empresa,
    Funcionario,
    HistorialAccion,
    Liquidacion,
    NominaMensual,
    CierreNomina,
    PermisoLicencia,
    Sucursal,
    Turno,
    Vacacion,
)

def _bloquear_si_no_admin_master(request):
    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if not admin_master:
        messages.error(request, "Este módulo solo está disponible para administración global.")
        return redirect("dashboard")

    return None

@login_required
def marcacion_manual(request):
    permiso = validar_permiso_o_redirigir(request, "asistencia", "puede_ver")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = MarcacionManualForm(request.POST)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            funcionario = form.cleaned_data["funcionario"]
            tipo = form.cleaned_data["tipo"]
            fecha = form.cleaned_data["fecha"]
            hora = form.cleaned_data["hora"]
            motivo = form.cleaned_data["motivo"]

            if not admin_master:
                if not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes registrar asistencia manual para otra empresa.")
                    return redirect("asistencia_marcar")

            fecha_hora_manual = timezone.make_aware(
                datetime.combine(fecha, hora)
            )

            asistencia, creada = Asistencia.objects.get_or_create(
                funcionario=funcionario,
                fecha=fecha,
            )

            if tipo in ["salida_almuerzo", "regreso_almuerzo"] and (
                not funcionario.turno or not funcionario.turno.usa_almuerzo
            ):
                messages.error(request, "Este funcionario no tiene un turno con almuerzo configurado.")
                return redirect("marcacion_manual")

            if tipo == "entrada":
                asistencia.hora_entrada = fecha_hora_manual
                asistencia.calcular_atraso()

            elif tipo == "salida_almuerzo":
                asistencia.hora_salida_almuerzo = fecha_hora_manual

            elif tipo == "regreso_almuerzo":
                asistencia.hora_regreso_almuerzo = fecha_hora_manual

            elif tipo == "salida":
                asistencia.hora_salida = fecha_hora_manual

            asistencia.origen_marcacion = "manual"
            asistencia.marcado_manual_por = request.user
            asistencia.motivo_marcacion_manual = motivo
            asistencia.fecha_hora_real_sistema = timezone.now()

            if tipo == "entrada":
                if asistencia.llego_tarde:
                    asistencia.observacion = f"📝 Entrada manual. Llegó con {asistencia.minutos_atraso} minuto(s) de atraso."
                else:
                    asistencia.observacion = "📝 Entrada manual registrada en horario."

            elif tipo == "salida_almuerzo":
                asistencia.observacion = "📝 Salida a almuerzo manual registrada."

            elif tipo == "regreso_almuerzo":
                asistencia.observacion = "📝 Regreso de almuerzo manual registrado."

            else:
                asistencia.observacion = "📝 Salida final manual registrada."

            asistencia.save()

            registrar_historial(
                request,
                "Asistencia",
                "Marcación manual",
                f"Marcación manual de {tipo} para {funcionario.nombre_completo}. "
                f"Hora registrada: {fecha_hora_manual.strftime('%d/%m/%Y %H:%M:%S')}. "
                f"Operador: {request.user}. Motivo: {motivo}"
            )

            messages.success(
                request,
                f"Marcación manual registrada correctamente para {funcionario.nombre_completo}."
            )
            return redirect("asistencia_marcar")
    else:
        form = MarcacionManualForm()

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "asistencias/marcacion_manual.html", {
        "form": form
    })


def registrar_historial(request, modulo, accion, descripcion):
    HistorialAccion.objects.create(
        usuario=request.user if request.user.is_authenticated else None,
        modulo=modulo,
        accion=accion,
        descripcion=descripcion,
    )


def funcionario_tiene_dia_libre(funcionario, fecha=None):
    fecha = fecha or timezone.localdate()
    dia_semana = fecha.weekday()

    return DiaLibre.objects.filter(
        funcionario=funcionario,
        activo=True,
        dia_semana=dia_semana,
    ).filter(
        Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=fecha),
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha),
    ).exists()


def contar_dias_libres_mes(funcionario, mes, anio):
    total = 0
    dias_mes = monthrange(anio, mes)[1]

    for dia in range(1, dias_mes + 1):
        fecha = date(anio, mes, dia)
        if funcionario_tiene_dia_libre(funcionario, fecha):
            total += 1

    return total


def calcular_icl_funcionario_mes(funcionario, mes, anio):
    dias_mes = monthrange(anio, mes)[1]
    total_dias_laborales_estimados = sum(
        1 for dia in range(1, dias_mes + 1)
        if date(anio, mes, dia).weekday() != 6
    )

    dias_libres_mes = contar_dias_libres_mes(funcionario, mes, anio)

    asistencias = Asistencia.objects.filter(
        funcionario=funcionario,
        fecha__year=anio,
        fecha__month=mes,
        hora_entrada__isnull=False,
    )

    asistencias_count = asistencias.count()
    atrasos_count = asistencias.filter(llego_tarde=True).count()

    permisos_aprobados = PermisoLicencia.objects.filter(
        funcionario=funcionario,
        estado=PermisoLicencia.Estados.APROBADO,
        fecha_desde__year=anio,
        fecha_desde__month=mes,
    ).count()

    vacaciones_aprobadas = Vacacion.objects.filter(
        funcionario=funcionario,
        estado=Vacacion.Estados.APROBADO,
        fecha_desde__year=anio,
        fecha_desde__month=mes,
    ).count()

    total_dias_laborales_reales = max(total_dias_laborales_estimados - dias_libres_mes, 0)
    ausencias_estimadas = max(total_dias_laborales_reales - asistencias_count, 0)
    ausencias_justificadas = permisos_aprobados + vacaciones_aprobadas
    ausencias_no_justificadas = max(ausencias_estimadas - ausencias_justificadas, 0)

    icl = 100 - (atrasos_count * 2) - (ausencias_no_justificadas * 5)
    icl = max(0, min(100, icl))

    return {
        "icl": icl,
        "asistencias": asistencias_count,
        "atrasos": atrasos_count,
        "ausencias_estimadas": ausencias_estimadas,
        "ausencias_no_justificadas": ausencias_no_justificadas,
        "dias_libres_mes": dias_libres_mes,
        "total_dias_laborales_reales": total_dias_laborales_reales,
    }


def generar_nomina_funcionario(funcionario, mes, anio):
    resumen_icl = calcular_icl_funcionario_mes(funcionario, mes, anio)

    salario_base = Decimal(funcionario.salario_base or 0).quantize(Decimal("0.01"))
    bono_base = Decimal(funcionario.bono or 0).quantize(Decimal("0.01"))
    bono_icl = (bono_base * Decimal(resumen_icl["icl"]) / Decimal("100")).quantize(Decimal("0.01"))
    salario_bruto = (salario_base + bono_icl).quantize(Decimal("0.01"))
    descuento_ips = funcionario.descuento_ips
    descuento_deudas = funcionario.descuento_deudas_mes

    salario_neto = salario_bruto - descuento_ips - descuento_deudas
    if salario_neto < 0:
        salario_neto = Decimal("0.00")
    salario_neto = salario_neto.quantize(Decimal("0.01"))

    defaults = {
        "salario_base": salario_base,
        "bono_base": bono_base,
        "bono_icl": bono_icl,
        "salario_bruto": salario_bruto,
        "descuento_ips": descuento_ips,
        "descuento_deudas": descuento_deudas,
        "salario_neto": salario_neto,
        "modalidad_cobro": funcionario.modalidad_cobro,
        "banco": funcionario.banco,
        "tipo_cuenta": funcionario.tipo_cuenta,
        "numero_cuenta": funcionario.numero_cuenta,
    }

    nomina, creada = NominaMensual.objects.update_or_create(
        funcionario=funcionario,
        mes=mes,
        anio=anio,
        defaults=defaults,
    )
    return nomina


@login_required
def dashboard(request):
    hoy = timezone.localdate()

    perm_funcionarios = tiene_permiso(request.user, "funcionarios", "puede_ver")
    perm_asistencia = tiene_permiso(request.user, "asistencia", "puede_ver")
    perm_deudas = tiene_permiso(request.user, "deudas", "puede_ver")
    perm_nomina = tiene_permiso(request.user, "nomina", "puede_ver")
    perm_icl = tiene_permiso(request.user, "icl", "puede_ver")
    perm_reportes = tiene_permiso(request.user, "reportes", "puede_ver")
    perm_dias_libres = tiene_permiso(request.user, "dias_libres", "puede_ver")
    perm_liquidacion = tiene_permiso(request.user, "liquidacion", "puede_ver")

    empresa_usuario = obtener_empresa_usuario(request.user)

    funcionarios_qs = Funcionario.objects.filter(activo=True)
    asistencias_hoy_qs = Asistencia.objects.select_related(
        "funcionario",
        "funcionario__turno"
    ).filter(
        fecha=hoy,
        funcionario__activo=True
    )
    deudas_qs = Deuda.objects.filter(activa=True)

    if not es_admin_master(request.user):
        if empresa_usuario:
            funcionarios_qs = funcionarios_qs.filter(sucursal_rel__empresa=empresa_usuario)
            asistencias_hoy_qs = asistencias_hoy_qs.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
            deudas_qs = deudas_qs.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            funcionarios_qs = funcionarios_qs.none()
            asistencias_hoy_qs = asistencias_hoy_qs.none()
            deudas_qs = deudas_qs.none()

    total_funcionarios = 0
    presentes_hoy = 0
    llegadas_tarde_hoy = 0
    salidas_hoy = 0
    pendientes_hoy = 0
    trabajando_hoy = 0
    en_almuerzo_hoy = 0
    finalizados_hoy = 0
    ultimas_marcaciones = []
    funcionarios_recientes = []
    total_salario_bruto = Decimal("0.00")
    total_salario_neto = Decimal("0.00")
    total_deudas_funcionarios = Decimal("0.00")

    if perm_funcionarios:
        total_funcionarios = funcionarios_qs.count()

        funcionarios_recientes = funcionarios_qs.select_related(
            "turno",
            "sucursal_rel",
            "sucursal_rel__empresa"
        ).order_by("-creado_en")[:6]

    if perm_asistencia:
        presentes_hoy = asistencias_hoy_qs.filter(hora_entrada__isnull=False).count()
        llegadas_tarde_hoy = asistencias_hoy_qs.filter(llego_tarde=True).count()
        salidas_hoy = asistencias_hoy_qs.filter(hora_salida__isnull=False).count()

        if perm_funcionarios:
            pendientes_hoy = max(total_funcionarios - presentes_hoy, 0)

        for asistencia in asistencias_hoy_qs:
            estado = asistencia.estado_jornada
            if estado == "Trabajando":
                trabajando_hoy += 1
            elif estado == "En almuerzo":
                en_almuerzo_hoy += 1
            elif estado == "Finalizado":
                finalizados_hoy += 1

        ultimas_marcaciones = asistencias_hoy_qs.order_by("-actualizado_en")[:8]

    if perm_nomina:
        for funcionario in funcionarios_qs:
            total_salario_bruto += funcionario.salario_bruto
            total_salario_neto += funcionario.salario_neto_estimado

    if perm_deudas:
        total_deudas_funcionarios = deudas_qs.aggregate(
            total=Sum("saldo_pendiente")
        )["total"] or Decimal("0.00")

    context = {
        "titulo": "Dashboard ClockIn",
        "hoy": hoy,
        "empresa_usuario": empresa_usuario,

        "total_funcionarios": total_funcionarios,
        "presentes_hoy": presentes_hoy,
        "llegadas_tarde_hoy": llegadas_tarde_hoy,
        "salidas_hoy": salidas_hoy,
        "pendientes_hoy": pendientes_hoy,
        "trabajando_hoy": trabajando_hoy,
        "en_almuerzo_hoy": en_almuerzo_hoy,
        "finalizados_hoy": finalizados_hoy,
        "ultimas_marcaciones": ultimas_marcaciones,
        "funcionarios_recientes": funcionarios_recientes,
        "total_salario_bruto": total_salario_bruto,
        "total_salario_neto": total_salario_neto,
        "total_deudas_funcionarios": total_deudas_funcionarios,

        "perm_funcionarios": perm_funcionarios,
        "perm_asistencia": perm_asistencia,
        "perm_deudas": perm_deudas,
        "perm_nomina": perm_nomina,
        "perm_icl": perm_icl,
        "perm_reportes": perm_reportes,
        "perm_dias_libres": perm_dias_libres,
        "perm_liquidacion": perm_liquidacion,
        "es_admin_master": es_admin_master(request.user),
    }
    return render(request, "core/dashboard.html", context)

@login_required
def empresas_lista(request):
    permiso = validar_permiso_o_redirigir(request, "empresas", "puede_ver")
    if permiso:
        return permiso
    bloqueo = _bloquear_si_no_admin_master(request)
    if bloqueo:
        return bloqueo

    q = request.GET.get("q", "").strip()
    empresas = Empresa.objects.all()

    if q:
        empresas = empresas.filter(
            Q(nombre__icontains=q) |
            Q(ruc__icontains=q)
        )

    return render(request, "core/empresas_lista.html", {
        "empresas": empresas.order_by("nombre"),
        "q": q,
    })


@login_required
def empresa_nueva(request):
    permiso = validar_permiso_o_redirigir(request, "empresas", "puede_crear")
    if permiso:
        return permiso
    bloqueo = _bloquear_si_no_admin_master(request)
    if bloqueo:
        return bloqueo

    if request.method == "POST":
        form = EmpresaForm(request.POST, request.FILES)
        if form.is_valid():
            empresa = form.save()
            registrar_historial(
                request,
                "Empresas",
                "Crear",
                f"Se creó la empresa {empresa.nombre}."
            )
            messages.success(request, "Empresa creada correctamente.")
            return redirect("empresas_lista")
    else:
        form = EmpresaForm()

    return render(request, "core/empresa_form.html", {
        "form": form,
        "titulo_form": "Nueva empresa",
        "boton_texto": "Guardar empresa",
    })


@login_required
def empresa_editar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "empresas", "puede_editar")
    if permiso:
        return permiso
    bloqueo = _bloquear_si_no_admin_master(request)
    if bloqueo:
        return bloqueo

    empresa = get_object_or_404(Empresa, pk=pk)

    if request.method == "POST":
        form = EmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            registrar_historial(
                request,
                "Empresas",
                "Editar",
                f"Se editó la empresa {empresa.nombre}."
            )
            messages.success(request, "Empresa actualizada correctamente.")
            return redirect("empresas_lista")
    else:
        form = EmpresaForm(instance=empresa)

    return render(request, "core/empresa_form.html", {
        "form": form,
        "titulo_form": f"Editar empresa: {empresa.nombre}",
        "boton_texto": "Guardar cambios",
        "empresa": empresa,
    })


@login_required
def empresa_toggle_activo(request, pk):
    permiso = validar_permiso_o_redirigir(request, "empresas", "puede_editar")
    if permiso:
        return permiso
    bloqueo = _bloquear_si_no_admin_master(request)
    if bloqueo:
        return bloqueo

    empresa = get_object_or_404(Empresa, pk=pk)
    empresa.activo = not empresa.activo
    empresa.save()

    estado = "activada" if empresa.activo else "inactivada"
    registrar_historial(
        request,
        "Empresas",
        "Cambio de estado",
        f"Empresa {empresa.nombre} fue {estado}."
    )
    messages.success(request, f"Empresa {estado} correctamente.")
    return redirect("empresas_lista")


@login_required
def sucursales_lista(request):
    permiso = validar_permiso_o_redirigir(request, "sucursales", "puede_ver")
    if permiso:
        return permiso

    q = request.GET.get("q", "").strip()
    empresa_id = request.GET.get("empresa", "").strip()

    sucursales = Sucursal.objects.select_related("empresa").all()

    if q:
        sucursales = sucursales.filter(
            Q(nombre__icontains=q) |
            Q(direccion__icontains=q) |
            Q(empresa__nombre__icontains=q)
        )

    if empresa_id:
        sucursales = sucursales.filter(empresa_id=empresa_id)

    empresas = Empresa.objects.filter(activo=True).order_by("nombre")

    return render(request, "core/sucursales_lista.html", {
        "sucursales": sucursales.order_by("empresa__nombre", "nombre"),
        "empresas": empresas,
        "empresa_id": empresa_id,
        "q": q,
    })


@login_required
def sucursal_nueva(request):
    permiso = validar_permiso_o_redirigir(request, "sucursales", "puede_crear")
    if permiso:
        return permiso

    if request.method == "POST":
        form = SucursalForm(request.POST)
        if form.is_valid():
            sucursal = form.save()
            registrar_historial(
                request,
                "Sucursales",
                "Crear",
                f"Se creó la sucursal {sucursal.nombre} de {sucursal.empresa.nombre}."
            )
            messages.success(request, "Sucursal creada correctamente.")
            return redirect("sucursales_lista")
    else:
        form = SucursalForm()

    return render(request, "core/sucursal_form.html", {
        "form": form,
        "titulo_form": "Nueva sucursal",
        "boton_texto": "Guardar sucursal",
    })


@login_required
def sucursal_editar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "sucursales", "puede_editar")
    if permiso:
        return permiso

    sucursal = get_object_or_404(Sucursal, pk=pk)

    if request.method == "POST":
        form = SucursalForm(request.POST, instance=sucursal)
        if form.is_valid():
            form.save()
            registrar_historial(
                request,
                "Sucursales",
                "Editar",
                f"Se editó la sucursal {sucursal.nombre} de {sucursal.empresa.nombre}."
            )
            messages.success(request, "Sucursal actualizada correctamente.")
            return redirect("sucursales_lista")
    else:
        form = SucursalForm(instance=sucursal)

    return render(request, "core/sucursal_form.html", {
        "form": form,
        "titulo_form": f"Editar sucursal: {sucursal.nombre}",
        "boton_texto": "Guardar cambios",
        "sucursal": sucursal,
    })


@login_required
def sucursal_toggle_activo(request, pk):
    permiso = validar_permiso_o_redirigir(request, "sucursales", "puede_editar")
    if permiso:
        return permiso

    sucursal = get_object_or_404(Sucursal, pk=pk)
    sucursal.activo = not sucursal.activo
    sucursal.save()

    estado = "activada" if sucursal.activo else "inactivada"
    registrar_historial(
        request,
        "Sucursales",
        "Cambio de estado",
        f"Sucursal {sucursal.nombre} fue {estado}."
    )
    messages.success(request, f"Sucursal {estado} correctamente.")
    return redirect("sucursales_lista")


@login_required
def obtener_sucursales_por_empresa(request):
    permiso = validar_permiso_o_redirigir(request, "funcionarios", "puede_ver")
    if permiso:
        return JsonResponse({"sucursales": []}, status=403)

    empresa_id = request.GET.get("empresa_id", "").strip()

    if not empresa_id:
        return JsonResponse({"sucursales": []})

    sucursales = Sucursal.objects.filter(
        empresa_id=empresa_id,
        activo=True
    ).order_by("nombre")

    data = [{"id": s.id, "nombre": s.nombre} for s in sucursales]
    return JsonResponse({"sucursales": data})


@login_required
def deudas_lista(request):
    permiso = validar_permiso_o_redirigir(request, "deudas", "puede_ver")
    if permiso:
        return permiso

    q = request.GET.get("q", "").strip()
    funcionario_id = request.GET.get("funcionario", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    deudas = Deuda.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa").all()

    if not admin_master:
        if empresa_usuario:
            deudas = deudas.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            deudas = deudas.none()

    if q:
        deudas = deudas.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(tipo__icontains=q)
        )

    if funcionario_id:
        deudas = deudas.filter(funcionario_id=funcionario_id)

    if admin_master:
        funcionarios = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")
    else:
        funcionarios = Funcionario.objects.filter(
            activo=True,
            sucursal_rel__empresa=empresa_usuario
        ).order_by("apellido", "nombre") if empresa_usuario else Funcionario.objects.none()

    return render(request, "core/deudas_lista.html", {
        "deudas": deudas.order_by("-fecha", "-creado_en"),
        "funcionarios": funcionarios,
        "funcionario_id": funcionario_id,
        "q": q,
    })


@login_required
def deuda_nueva(request):
    permiso = validar_permiso_o_redirigir(request, "deudas", "puede_crear")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = DeudaForm(request.POST)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            deuda = form.save(commit=False)

            if not admin_master:
                if not deuda.funcionario.sucursal_rel or deuda.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes crear deudas para otra empresa.")
                    return redirect("deudas_lista")

            deuda.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Deudas",
                "Crear",
                f"Se creó deuda para {deuda.funcionario.nombre_completo} por {deuda.saldo_pendiente}."
            )
            messages.success(request, "Deuda creada correctamente.")
            return redirect("deudas_lista")
    else:
        form = DeudaForm()
        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/deuda_form.html", {
        "form": form,
        "titulo_form": "Nueva deuda",
        "boton_texto": "Guardar deuda",
    })


@login_required
def deuda_editar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "deudas", "puede_editar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    deuda = get_object_or_404(Deuda, pk=pk)

    if not admin_master:
        if not deuda.funcionario.sucursal_rel or deuda.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes editar deudas de otra empresa.")
            return redirect("deudas_lista")

    if request.method == "POST":
        form = DeudaForm(request.POST, instance=deuda)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            deuda_editada = form.save(commit=False)

            if not admin_master:
                if not deuda_editada.funcionario.sucursal_rel or deuda_editada.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes mover deudas a otra empresa.")
                    return redirect("deudas_lista")

            deuda_editada.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Deudas",
                "Editar",
                f"Se editó deuda de {deuda_editada.funcionario.nombre_completo}."
            )
            messages.success(request, "Deuda actualizada correctamente.")
            return redirect("deudas_lista")
    else:
        form = DeudaForm(instance=deuda)
        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/deuda_form.html", {
        "form": form,
        "titulo_form": f"Editar deuda: {deuda.funcionario.nombre_completo}",
        "boton_texto": "Guardar cambios",
        "deuda": deuda,
    })


@login_required
def deuda_toggle_activa(request, pk):
    permiso = validar_permiso_o_redirigir(request, "deudas", "puede_editar")
    if permiso:
        return permiso

    deuda = get_object_or_404(Deuda, pk=pk)
    deuda.activa = not deuda.activa
    deuda.save()

    estado = "activada" if deuda.activa else "inactivada"
    registrar_historial(
        request,
        "Deudas",
        "Cambio de estado",
        f"Deuda de {deuda.funcionario.nombre_completo} fue {estado}."
    )
    messages.success(request, f"Deuda {estado} correctamente.")
    return redirect("deudas_lista")


@login_required
def funcionarios_lista(request):
    permiso = validar_permiso_o_redirigir(request, "funcionarios", "puede_ver")
    if permiso:
        return permiso

    q = request.GET.get("q", "").strip()
    empresa_id = request.GET.get("empresa", "").strip()
    sucursal_id = request.GET.get("sucursal", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    funcionarios = Funcionario.objects.select_related(
        "turno",
        "sucursal_rel",
        "sucursal_rel__empresa"
    ).all()

    if not admin_master:
        if empresa_usuario:
            funcionarios = funcionarios.filter(sucursal_rel__empresa=empresa_usuario)
        else:
            funcionarios = funcionarios.none()

    if q:
        funcionarios = funcionarios.filter(
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q) |
            Q(cedula__icontains=q) |
            Q(cargo__icontains=q) |
            Q(sector__icontains=q) |
            Q(sucursal__icontains=q) |
            Q(sucursal_rel__nombre__icontains=q) |
            Q(sucursal_rel__empresa__nombre__icontains=q) |
            Q(turno__nombre__icontains=q)
        )

    if admin_master:
        if empresa_id:
            funcionarios = funcionarios.filter(sucursal_rel__empresa_id=empresa_id)
    else:
        if empresa_usuario:
            empresa_id = str(empresa_usuario.id)

    if sucursal_id:
        funcionarios = funcionarios.filter(sucursal_rel_id=sucursal_id)

    if admin_master:
        empresas = Empresa.objects.filter(activo=True).order_by("nombre")
        sucursales = Sucursal.objects.filter(activo=True).order_by("nombre")
        if empresa_id:
            sucursales = sucursales.filter(empresa_id=empresa_id)
    else:
        empresas = Empresa.objects.filter(id=empresa_usuario.id) if empresa_usuario else Empresa.objects.none()
        sucursales = Sucursal.objects.filter(
            activo=True,
            empresa=empresa_usuario
        ).order_by("nombre") if empresa_usuario else Sucursal.objects.none()

    context = {
        "funcionarios": funcionarios.order_by("apellido", "nombre"),
        "q": q,
        "empresas": empresas,
        "sucursales": sucursales,
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    }
    return render(request, "core/funcionarios_lista.html", context)


@login_required
def funcionario_nuevo(request):
    permiso = validar_permiso_o_redirigir(request, "funcionarios", "puede_crear")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = FuncionarioForm(request.POST, request.FILES)


        if not admin_master and empresa_usuario:
            form.fields["sucursal_rel"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

        if form.is_valid():
            funcionario = form.save(commit=False)

            if not admin_master:
                if not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes crear funcionarios fuera de tu empresa.")
                    return redirect("funcionarios_lista")

            funcionario.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Funcionarios",
                "Crear",
                f"Se creó el funcionario {funcionario.nombre_completo} (CI: {funcionario.cedula})."
            )
            messages.success(request, "Funcionario creado correctamente.")
            return redirect("funcionarios_lista")
    else:
        form = FuncionarioForm()
        if not admin_master and empresa_usuario:
            form.fields["sucursal_rel"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

        if not admin_master and empresa_usuario:
            form.fields["turno"].queryset = Turno.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")
        elif admin_master:
            form.fields["turno"].queryset = Turno.objects.filter(
                activo=True
            ).order_by("nombre")

    return render(request, "core/funcionario_form.html", {
        "form": form,
        "titulo_form": "Nuevo funcionario",
        "boton_texto": "Guardar funcionario",
    })


@login_required
def funcionario_editar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "funcionarios", "puede_editar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    funcionario = get_object_or_404(Funcionario, pk=pk)

    if not admin_master:
        if not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes editar funcionarios de otra empresa.")
            return redirect("funcionarios_lista")

    if request.method == "POST":
        form = FuncionarioForm(request.POST, request.FILES, instance=funcionario)

        if not admin_master and empresa_usuario:
            form.fields["sucursal_rel"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

        if form.is_valid():
            funcionario_editado = form.save(commit=False)

            if not admin_master:
                if not funcionario_editado.sucursal_rel or funcionario_editado.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes mover un funcionario a otra empresa.")
                    return redirect("funcionarios_lista")

            funcionario_editado.save()
            form.save_m2m()

            if not admin_master and empresa_usuario:
                form.fields["turno"].queryset = Turno.objects.filter(
                    activo=True,
                    empresa=empresa_usuario
                ).order_by("nombre")
            elif admin_master:
                form.fields["turno"].queryset = Turno.objects.filter(
                    activo=True
                ).order_by("nombre")

            registrar_historial(
                request,
                "Funcionarios",
                "Editar",
                f"Se editó el funcionario {funcionario_editado.nombre_completo} (CI: {funcionario_editado.cedula})."
            )
            messages.success(request, "Funcionario actualizado correctamente.")
            return redirect("funcionarios_lista")
    else:
        form = FuncionarioForm(instance=funcionario)
        if not admin_master and empresa_usuario:
            form.fields["sucursal_rel"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

    return render(request, "core/funcionario_form.html", {
        "form": form,
        "titulo_form": f"Editar funcionario: {funcionario.nombre_completo}",
        "boton_texto": "Guardar cambios",
        "funcionario": funcionario,
    })


@login_required
def funcionario_toggle_activo(request, pk):
    permiso = validar_permiso_o_redirigir(request, "funcionarios", "puede_editar")
    if permiso:
        return permiso

    funcionario = get_object_or_404(Funcionario, pk=pk)
    funcionario.activo = not funcionario.activo
    funcionario.save()

    estado = "activado" if funcionario.activo else "inactivado"
    registrar_historial(
        request,
        "Funcionarios",
        "Cambio de estado",
        f"Funcionario {funcionario.nombre_completo} fue {estado}."
    )
    messages.success(request, f"Funcionario {estado} correctamente.")
    return redirect("funcionarios_lista")


@login_required
def turnos_lista(request):
    permiso = validar_permiso_o_redirigir(request, "turnos", "puede_ver")
    if permiso:
        return permiso

    q = request.GET.get("q", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    turnos = Turno.objects.select_related("empresa").all()

    if not admin_master:
        if empresa_usuario:
            turnos = turnos.filter(empresa=empresa_usuario)
        else:
            turnos = turnos.none()

    if q:
        turnos = turnos.filter(nombre__icontains=q)

    return render(request, "core/turnos_lista.html", {
        "turnos": turnos.order_by("nombre"),
        "q": q,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def turno_nuevo(request):
    permiso = validar_permiso_o_redirigir(request, "turnos", "puede_crear")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = TurnoForm(request.POST)

        if not admin_master:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id) if empresa_usuario else Empresa.objects.none()

        if form.is_valid():
            turno = form.save(commit=False)

            if admin_master:
                if not turno.empresa:
                    messages.error(request, "Debes seleccionar una empresa para el turno.")
                    return render(request, "core/turno_form.html", {
                        "form": form,
                        "titulo_form": "Nuevo turno",
                        "boton_texto": "Guardar turno",
                    })
            else:
                if not empresa_usuario:
                    messages.error(request, "Tu usuario no tiene empresa asignada.")
                    return redirect("turnos_lista")
                turno.empresa = empresa_usuario

            turno.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Turnos",
                "Crear",
                f"Se creó el turno {turno.nombre} para la empresa {turno.empresa.nombre if turno.empresa else 'Sin empresa'}."
            )
            messages.success(request, "Turno creado correctamente.")
            return redirect("turnos_lista")
    else:
        form = TurnoForm()

        if admin_master:
            form.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")
        else:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id) if empresa_usuario else Empresa.objects.none()
            if empresa_usuario:
                form.fields["empresa"].initial = empresa_usuario

    return render(request, "core/turno_form.html", {
        "form": form,
        "titulo_form": "Nuevo turno",
        "boton_texto": "Guardar turno",
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def turno_editar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "turnos", "puede_editar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    turno = get_object_or_404(Turno.objects.select_related("empresa"), pk=pk)

    if not admin_master:
        if turno.empresa != empresa_usuario:
            messages.error(request, "No puedes editar turnos de otra empresa.")
            return redirect("turnos_lista")

    if request.method == "POST":
        form = TurnoForm(request.POST, instance=turno)

        if not admin_master:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id) if empresa_usuario else Empresa.objects.none()

        if form.is_valid():
            turno_editado = form.save(commit=False)

            if admin_master:
                if not turno_editado.empresa:
                    messages.error(request, "Debes seleccionar una empresa para el turno.")
                    return render(request, "core/turno_form.html", {
                        "form": form,
                        "titulo_form": "Editar turno",
                        "boton_texto": "Guardar cambios",
                        "turno": turno,
                    })
            else:
                turno_editado.empresa = empresa_usuario

            turno_editado.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Turnos",
                "Editar",
                f"Se editó el turno {turno_editado.nombre}."
            )
            messages.success(request, "Turno actualizado correctamente.")
            return redirect("turnos_lista")
    else:
        form = TurnoForm(instance=turno)

        if admin_master:
            form.fields["empresa"].queryset = Empresa.objects.filter(activo=True).order_by("nombre")
        else:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id) if empresa_usuario else Empresa.objects.none()

    return render(request, "core/turno_form.html", {
        "form": form,
        "titulo_form": "Editar turno",
        "boton_texto": "Guardar cambios",
        "turno": turno,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def turno_toggle_activo(request, pk):
    permiso = validar_permiso_o_redirigir(request, "turnos", "puede_editar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    turno = get_object_or_404(Turno.objects.select_related("empresa"), pk=pk)

    if not admin_master:
        if turno.empresa != empresa_usuario:
            messages.error(request, "No puedes cambiar turnos de otra empresa.")
            return redirect("turnos_lista")

    turno.activo = not turno.activo
    turno.save(update_fields=["activo"])

    registrar_historial(
        request,
        "Turnos",
        "Cambio de estado",
        f"Se cambió el estado del turno {turno.nombre} a {'Activo' if turno.activo else 'Inactivo'}."
    )
    messages.success(request, "Estado del turno actualizado correctamente.")
    return redirect("turnos_lista")

@login_required
def asistencia_marcar(request):
    permiso = validar_permiso_o_redirigir(request, "asistencia", "puede_ver")
    if permiso:
        return permiso

    hoy = timezone.localdate()
    resultado = None

    sucursal_id = request.GET.get("sucursal", "").strip()
    q = request.GET.get("q", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        permiso_post = validar_permiso_o_redirigir(request, "asistencia", "puede_crear")
        if permiso_post:
            return permiso_post

        form = MarcacionForm(request.POST)
        if form.is_valid():
            cedula = form.cleaned_data["cedula"].strip()

            try:
                funcionario = Funcionario.objects.select_related("turno", "sucursal_rel", "sucursal_rel__empresa").get(
                    cedula=cedula,
                    activo=True
                )
            except Funcionario.DoesNotExist:
                messages.error(request, "No se encontró un funcionario activo con esa cédula.")
                funcionario = None

            if funcionario and not admin_master:
                if not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes registrar asistencia para otra empresa.")
                    funcionario = None

            if funcionario:
                if funcionario_tiene_dia_libre(funcionario, hoy):
                    messages.info(
                        request,
                        f"{funcionario.nombre_completo} tiene día libre hoy. No corresponde asistencia."
                    )
                    resultado = {
                        "tipo": "dia_libre",
                        "funcionario": funcionario,
                        "hora": timezone.localtime(),
                        "turno": funcionario.turno.nombre if funcionario.turno else "-",
                        "atraso": 0,
                        "llego_tarde": False,
                    }
                else:
                    asistencia, creada = Asistencia.objects.get_or_create(
                        funcionario=funcionario,
                        fecha=hoy
                    )

                    ahora = timezone.localtime()

                    if not funcionario.turno:
                        messages.error(request, "El funcionario no tiene un turno asignado.")
                    else:
                        siguiente = asistencia.siguiente_marcacion

                        if siguiente == "entrada":
                            asistencia.hora_entrada = ahora
                            asistencia.calcular_atraso()

                            if asistencia.llego_tarde:
                                asistencia.observacion = f"Llegó con {asistencia.minutos_atraso} minuto(s) de atraso."
                            else:
                                asistencia.observacion = "Entrada registrada en horario."

                            asistencia.save()

                            registrar_historial(
                                request,
                                "Asistencia",
                                "Entrada",
                                f"Se registró entrada de {funcionario.nombre_completo} a las {ahora.strftime('%H:%M:%S')}."
                            )

                            resultado = {
                                "tipo": "entrada",
                                "funcionario": funcionario,
                                "hora": ahora,
                                "turno": funcionario.turno.nombre,
                                "atraso": asistencia.minutos_atraso,
                                "llego_tarde": asistencia.llego_tarde,
                            }
                            messages.success(request, "Entrada registrada correctamente.")

                        elif siguiente == "salida_almuerzo":
                            asistencia.hora_salida_almuerzo = ahora
                            asistencia.observacion = "Salida a almuerzo registrada correctamente."
                            asistencia.save()

                            registrar_historial(
                                request,
                                "Asistencia",
                                "Salida a almuerzo",
                                f"Se registró salida a almuerzo de {funcionario.nombre_completo} a las {ahora.strftime('%H:%M:%S')}."
                            )

                            resultado = {
                                "tipo": "salida_almuerzo",
                                "funcionario": funcionario,
                                "hora": ahora,
                                "turno": funcionario.turno.nombre,
                                "atraso": asistencia.minutos_atraso,
                                "llego_tarde": asistencia.llego_tarde,
                            }
                            messages.success(request, "Salida a almuerzo registrada correctamente.")

                        elif siguiente == "regreso_almuerzo":
                            asistencia.hora_regreso_almuerzo = ahora
                            if asistencia.observacion:
                                asistencia.observacion += " Regreso de almuerzo registrado correctamente."
                            else:
                                asistencia.observacion = "Regreso de almuerzo registrado correctamente."
                            asistencia.save()

                            registrar_historial(
                                request,
                                "Asistencia",
                                "Regreso de almuerzo",
                                f"Se registró regreso de almuerzo de {funcionario.nombre_completo} a las {ahora.strftime('%H:%M:%S')}."
                            )

                            resultado = {
                                "tipo": "regreso_almuerzo",
                                "funcionario": funcionario,
                                "hora": ahora,
                                "turno": funcionario.turno.nombre,
                                "atraso": asistencia.minutos_atraso,
                                "llego_tarde": asistencia.llego_tarde,
                            }
                            messages.success(request, "Regreso de almuerzo registrado correctamente.")

                        elif siguiente == "salida":
                            asistencia.hora_salida = ahora
                            if asistencia.observacion:
                                asistencia.observacion += " Salida final registrada correctamente."
                            else:
                                asistencia.observacion = "Salida final registrada correctamente."
                            asistencia.save()

                            registrar_historial(
                                request,
                                "Asistencia",
                                "Salida final",
                                f"Se registró salida final de {funcionario.nombre_completo} a las {ahora.strftime('%H:%M:%S')}."
                            )

                            resultado = {
                                "tipo": "salida",
                                "funcionario": funcionario,
                                "hora": ahora,
                                "turno": funcionario.turno.nombre,
                                "atraso": asistencia.minutos_atraso,
                                "llego_tarde": asistencia.llego_tarde,
                            }
                            messages.success(request, "Salida final registrada correctamente.")

                        else:
                            messages.warning(request, "El funcionario ya completó todas sus marcaciones del día.")
    else:
        form = MarcacionForm()

    asistencias_hoy = Asistencia.objects.select_related(
        "funcionario",
        "funcionario__turno",
        "funcionario__sucursal_rel",
        "funcionario__sucursal_rel__empresa"
    ).filter(fecha=hoy)

    if not admin_master:
        if empresa_usuario:
            asistencias_hoy = asistencias_hoy.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            asistencias_hoy = asistencias_hoy.none()

    if sucursal_id:
        asistencias_hoy = asistencias_hoy.filter(funcionario__sucursal_rel_id=sucursal_id)

    if q:
        asistencias_hoy = asistencias_hoy.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q)
        )

    if admin_master:
        sucursales = Sucursal.objects.filter(activo=True).order_by("empresa__nombre", "nombre")
    else:
        sucursales = Sucursal.objects.filter(
            activo=True,
            empresa=empresa_usuario
        ).order_by("nombre") if empresa_usuario else Sucursal.objects.none()        

    asistencias_hoy = asistencias_hoy.order_by("-hora_entrada")

    return render(request, "core/asistencia_marcar.html", {
        "form": form,
        "resultado": resultado,
        "asistencias_hoy": asistencias_hoy,
        "hoy": hoy,
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "q": q,
    })


@login_required
def permisos_lista(request):
    permiso = validar_permiso_o_redirigir(request, "permisos", "puede_ver")
    if permiso:
        return permiso

    q = request.GET.get("q", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    permisos = PermisoLicencia.objects.select_related(
        "funcionario",
        "funcionario__sucursal_rel",
        "funcionario__sucursal_rel__empresa"
    ).all()

    if not admin_master:
        if empresa_usuario:
            permisos = permisos.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            permisos = permisos.none()

    if q:
        permisos = permisos.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q) |
            Q(tipo__icontains=q) |
            Q(estado__icontains=q)
        )

    return render(request, "core/permisos_lista.html", {
        "permisos": permisos,
        "q": q,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def permiso_nuevo(request):
    permiso_acc = validar_permiso_o_redirigir(request, "permisos", "puede_crear")
    if permiso_acc:
        return permiso_acc

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = PermisoLicenciaForm(request.POST, request.FILES)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            permiso_obj = form.save(commit=False)

            if not admin_master:
                if not permiso_obj.funcionario.sucursal_rel or permiso_obj.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes crear permisos para otra empresa.")
                    return redirect("permisos_lista")

            permiso_obj.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Permisos/Licencias",
                "Crear",
                f"Se creó {permiso_obj.get_tipo_display()} para {permiso_obj.funcionario.nombre_completo} del {permiso_obj.fecha_desde} al {permiso_obj.fecha_hasta}."
            )
            messages.success(request, "Permiso/licencia creado correctamente.")
            return redirect("permisos_lista")
    else:
        form = PermisoLicenciaForm()

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/permiso_form.html", {
        "form": form,
        "titulo_form": "Nuevo permiso / licencia",
        "boton_texto": "Guardar permiso",
    })


@login_required
def permiso_editar(request, pk):
    permiso_acc = validar_permiso_o_redirigir(request, "permisos", "puede_editar")
    if permiso_acc:
        return permiso_acc

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    permiso_obj = get_object_or_404(
        PermisoLicencia.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not permiso_obj.funcionario.sucursal_rel or permiso_obj.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes editar permisos de otra empresa.")
            return redirect("permisos_lista")

    if request.method == "POST":
        form = PermisoLicenciaForm(request.POST, request.FILES, instance=permiso_obj)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            permiso_editado = form.save(commit=False)

            if not admin_master:
                if not permiso_editado.funcionario.sucursal_rel or permiso_editado.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes mover permisos a otra empresa.")
                    return redirect("permisos_lista")

            permiso_editado.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Permisos/Licencias",
                "Editar",
                f"Se editó {permiso_editado.get_tipo_display()} de {permiso_editado.funcionario.nombre_completo}. Estado actual: {permiso_editado.get_estado_display()}."
            )
            messages.success(request, "Permiso/licencia actualizado correctamente.")
            return redirect("permisos_lista")
    else:
        form = PermisoLicenciaForm(instance=permiso_obj)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/permiso_form.html", {
        "form": form,
        "titulo_form": "Editar permiso / licencia",
        "boton_texto": "Guardar cambios",
        "permiso": permiso_obj,
    })


@login_required
def vacaciones_lista(request):
    permiso = validar_permiso_o_redirigir(request, "vacaciones", "puede_ver")
    if permiso:
        return permiso
    
    alertas_vacaciones = []

    q = request.GET.get("q", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    vacaciones = Vacacion.objects.select_related(
        "funcionario",
        "funcionario__sucursal_rel",
        "funcionario__sucursal_rel__empresa"
    ).all()

    if not admin_master:
        if empresa_usuario:
            vacaciones = vacaciones.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            vacaciones = vacaciones.none()

    if q:
        vacaciones = vacaciones.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q) |
            Q(estado__icontains=q)
        )

    if admin_master:
        funcionarios_resumen = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")
    else:
        funcionarios_resumen = Funcionario.objects.filter(
            activo=True,
            sucursal_rel__empresa=empresa_usuario
        ).order_by("apellido", "nombre") if empresa_usuario else Funcionario.objects.none()

        alertas_vacaciones = []

        for funcionario in funcionarios_resumen:
            alerta = calcular_alertas_vacaciones(funcionario)
            if alerta:
                alertas_vacaciones.append({
                    "funcionario": funcionario,
                    "alerta": alerta,
                })

    return render(request, "core/vacaciones_lista.html", {
        "vacaciones": vacaciones,
        "alertas_vacaciones": alertas_vacaciones,
        "funcionarios_resumen": funcionarios_resumen,
        "q": q,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def vacacion_nueva(request):
    permiso_acc = validar_permiso_o_redirigir(request, "vacaciones", "puede_crear")
    if permiso_acc:
        return permiso_acc

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = VacacionForm(request.POST)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            vacacion = form.save(commit=False)

            if not admin_master:
                if not vacacion.funcionario.sucursal_rel or vacacion.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes crear vacaciones para otra empresa.")
                    return redirect("vacaciones_lista")

            vacacion.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Vacaciones",
                "Crear",
                f"Se creó vacación para {vacacion.funcionario.nombre_completo} del {vacacion.fecha_desde} al {vacacion.fecha_hasta} por {vacacion.dias_solicitados} día(s)."
            )
            messages.success(request, "Vacación registrada correctamente.")
            return redirect("vacaciones_lista")
    else:
        form = VacacionForm()

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/vacacion_form.html", {
        "form": form,
        "titulo_form": "Nueva vacación",
        "boton_texto": "Guardar vacación",
        "funcionarios_json": [
    {
        "id": f.id,
        "nombre": f.nombre_completo,
        "dias": f.saldo_vacaciones,
    }
    for f in form.fields["funcionario"].queryset
],
    })

@login_required
def vacacion_editar(request, pk):
    permiso_acc = validar_permiso_o_redirigir(request, "vacaciones", "puede_editar")
    if permiso_acc:
        return permiso_acc

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    vacacion = get_object_or_404(
        Vacacion.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not vacacion.funcionario.sucursal_rel or vacacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes editar vacaciones de otra empresa.")
            return redirect("vacaciones_lista")

    if request.method == "POST":
        form = VacacionForm(request.POST, instance=vacacion)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            vacacion_editada = form.save(commit=False)

            if not admin_master:
                if not vacacion_editada.funcionario.sucursal_rel or vacacion_editada.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes mover vacaciones a otra empresa.")
                    return redirect("vacaciones_lista")

            vacacion_editada.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Vacaciones",
                "Editar",
                f"Se editó vacación de {vacacion_editada.funcionario.nombre_completo}. Estado actual: {vacacion_editada.get_estado_display()}."
            )
            messages.success(request, "Vacación actualizada correctamente.")
            return redirect("vacaciones_lista")
    else:
        form = VacacionForm(instance=vacacion)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/vacacion_form.html", {
        "form": form,
        "titulo_form": "Editar vacación",
        "boton_texto": "Guardar cambios",
        "vacacion": vacacion,
        "funcionarios_json": [
    {
        "id": f.id,
        "nombre": f.nombre_completo,
        "dias": f.saldo_vacaciones,
    }
    for f in form.fields["funcionario"].queryset
],
    })

@login_required
def vacacion_notificacion_pdf(request, pk):
    permiso = validar_permiso_o_redirigir(request, "vacaciones", "puede_ver")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    vacacion = get_object_or_404(
        Vacacion.objects.select_related(
            "funcionario",
            "funcionario__sucursal_rel",
            "funcionario__sucursal_rel__empresa"
        ),
        pk=pk
    )

    if not admin_master:
        if not vacacion.funcionario.sucursal_rel or vacacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes generar notificación de otra empresa.")
            return redirect("vacaciones_lista")

    funcionario = vacacion.funcionario
    config = ConfiguracionGeneral.obtener()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloVacaciones",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="TextoVacaciones",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    ))

    elementos = []

    empresa_nombre = funcionario.empresa_mostrar
    sucursal_nombre = funcionario.sucursal_mostrar
    fecha_emision = timezone.localdate()

    elementos.append(Paragraph(config.nombre_sistema or "ClockIn", styles["TituloVacaciones"]))
    elementos.append(Paragraph("NOTIFICACIÓN DE VACACIONES ANUALES REMUNERADAS", styles["TituloVacaciones"]))
    elementos.append(Spacer(1, 10))

    datos = [
        ["Empresa", empresa_nombre],
        ["Sucursal", sucursal_nombre],
        ["Fecha de emisión", fecha_emision.strftime("%d/%m/%Y")],
        ["Funcionario", funcionario.nombre_completo],
        ["Cédula", funcionario.cedula],
        ["Cargo", funcionario.cargo or "-"],
        ["Fecha desde", vacacion.fecha_desde.strftime("%d/%m/%Y")],
        ["Fecha hasta", vacacion.fecha_hasta.strftime("%d/%m/%Y")],
        ["Días otorgados", str(vacacion.dias_solicitados)],
    ]

    tabla = Table(datos, colWidths=[55 * mm, 105 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1d4ed8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 16))

    texto = f"""
    Por medio de la presente, se comunica formalmente al trabajador <b>{funcionario.nombre_completo}</b>,
    con C.I. N° <b>{funcionario.cedula}</b>, que hará uso de sus vacaciones anuales remuneradas
    desde el día <b>{vacacion.fecha_desde.strftime("%d/%m/%Y")}</b> hasta el día
    <b>{vacacion.fecha_hasta.strftime("%d/%m/%Y")}</b>, por un total de
    <b>{vacacion.dias_solicitados}</b> día(s).
    <br/><br/>
    Esta comunicación se realiza por escrito con la anticipación correspondiente, conforme a la normativa laboral vigente.
    Las vacaciones deberán iniciar en día lunes o en el siguiente día hábil si aquel fuese feriado.
    """

    elementos.append(Paragraph(texto, styles["TextoVacaciones"]))
    elementos.append(Spacer(1, 34))

    firmas = Table([
        ["_______________________________", "_______________________________"],
        ["Firma del empleador / RRHH", "Firma del funcionario"],
        ["", ""],
        ["Fecha de recepción: ____/____/______", "Aclaración: ____________________"],
    ], colWidths=[80 * mm, 80 * mm])

    firmas.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elementos.append(firmas)

    doc.build(elementos)

    pdf = buffer.getvalue()
    buffer.close()

    registrar_historial(
        request,
        "Vacaciones",
        "Notificación PDF",
        f"Se generó notificación de vacaciones para {funcionario.nombre_completo} del {vacacion.fecha_desde} al {vacacion.fecha_hasta}."
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="notificacion_vacaciones_{funcionario.cedula}_{vacacion.id}.pdf"'
    response.write(pdf)
    return response

def sumar_meses(fecha, meses):
    mes = fecha.month - 1 + meses
    anio = fecha.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha.day, monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def calcular_alertas_vacaciones(funcionario):
    if not funcionario.fecha_ingreso:
        return None

    hoy = timezone.localdate()
    ultimo_aniversario = date(hoy.year, funcionario.fecha_ingreso.month, funcionario.fecha_ingreso.day)

    if ultimo_aniversario > hoy:
        ultimo_aniversario = date(hoy.year - 1, funcionario.fecha_ingreso.month, funcionario.fecha_ingreso.day)

    vencimiento = sumar_meses(ultimo_aniversario, 6)
    dias_para_vencer = (vencimiento - hoy).days

    if funcionario.saldo_vacaciones <= 0:
        return None

    if dias_para_vencer < 0:
        return {
            "tipo": "vencida",
            "texto": f"Vacaciones vencidas desde {vencimiento.strftime('%d/%m/%Y')}",
            "vencimiento": vencimiento,
        }

    if dias_para_vencer <= 45:
        return {
            "tipo": "proxima",
            "texto": f"Vacaciones próximas a vencer en {dias_para_vencer} día(s)",
            "vencimiento": vencimiento,
        }

    return None

@login_required
def icl_lista(request):
    permiso = validar_permiso_o_redirigir(request, "icl", "puede_ver")
    if permiso:
        return permiso

    hoy = timezone.localdate()

    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    dias_mes = monthrange(anio, mes)[1]
    total_dias_laborales_estimados = sum(
        1 for dia in range(1, dias_mes + 1)
        if date(anio, mes, dia).weekday() != 6
    )

    funcionarios = Funcionario.objects.filter(
        activo=True
    ).select_related("turno").order_by("apellido", "nombre")

    if not admin_master:
        if empresa_usuario:
            funcionarios = funcionarios.filter(sucursal_rel__empresa=empresa_usuario)
        else:
            funcionarios = funcionarios.none()

    resultados = []

    for funcionario in funcionarios:
        asistencias = Asistencia.objects.filter(
            funcionario=funcionario,
            fecha__year=anio,
            fecha__month=mes,
            hora_entrada__isnull=False,
        )

        asistencias_count = asistencias.count()
        atrasos_count = asistencias.filter(llego_tarde=True).count()

        permisos_aprobados = PermisoLicencia.objects.filter(
            funcionario=funcionario,
            estado=PermisoLicencia.Estados.APROBADO,
            fecha_desde__year=anio,
            fecha_desde__month=mes,
        ).count()

        vacaciones_aprobadas = Vacacion.objects.filter(
            funcionario=funcionario,
            estado=Vacacion.Estados.APROBADO,
            fecha_desde__year=anio,
            fecha_desde__month=mes,
        ).count()

        dias_libres_mes = contar_dias_libres_mes(funcionario, mes, anio)
        total_dias_laborales_reales = max(total_dias_laborales_estimados - dias_libres_mes, 0)
        ausencias_estimadas = max(total_dias_laborales_reales - asistencias_count, 0)
        ausencias_justificadas = permisos_aprobados + vacaciones_aprobadas
        ausencias_no_justificadas = max(ausencias_estimadas - ausencias_justificadas, 0)

        icl = 100 - (atrasos_count * 2) - (ausencias_no_justificadas * 5)
        icl = max(0, min(100, icl))

        bono_base = Decimal(funcionario.bono or 0).quantize(Decimal("0.01"))
        bono_pagable_icl = (bono_base * Decimal(icl) / Decimal("100")).quantize(Decimal("0.01"))
        salario_base = Decimal(funcionario.salario_base or 0).quantize(Decimal("0.01"))
        salario_bruto_mes = (salario_base + bono_pagable_icl).quantize(Decimal("0.01"))
        deudas_mes = funcionario.descuento_deudas_mes
        salario_neto_mes = salario_bruto_mes - funcionario.descuento_ips - deudas_mes
        if salario_neto_mes < 0:
            salario_neto_mes = Decimal("0.00")
        salario_neto_mes = salario_neto_mes.quantize(Decimal("0.01"))

        resultados.append({
            "funcionario": funcionario,
            "asistencias": asistencias_count,
            "atrasos": atrasos_count,
            "ausencias_estimadas": ausencias_estimadas,
            "permisos_aprobados": permisos_aprobados,
            "vacaciones_aprobadas": vacaciones_aprobadas,
            "ausencias_no_justificadas": ausencias_no_justificadas,
            "dias_libres_mes": dias_libres_mes,
            "icl": icl,
            "bono_base": bono_base,
            "bono_pagable_icl": bono_pagable_icl,
            "salario_base_mes": salario_base,
            "salario_bruto": salario_bruto_mes,
            "salario_neto": salario_neto_mes,
            "deudas_mes": deudas_mes,
        })

    resultados.sort(
        key=lambda x: (-x["icl"], x["funcionario"].apellido, x["funcionario"].nombre)
    )

    top_5 = resultados[:5]
    peores_5 = sorted(
        resultados,
        key=lambda x: (x["icl"], x["funcionario"].apellido, x["funcionario"].nombre)
    )[:5]

    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]
    anios = list(range(hoy.year - 2, hoy.year + 2))

    return render(request, "core/icl_lista.html", {
        "resultados": resultados,
        "top_5": top_5,
        "peores_5": peores_5,
        "mes": mes,
        "anio": anio,
        "meses": meses,
        "anios": anios,
        "total_dias_laborales_estimados": total_dias_laborales_estimados,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def reportes(request):
    permiso = validar_permiso_o_redirigir(request, "reportes", "puede_ver")
    if permiso:
        return permiso

    hoy = timezone.localdate()

    fecha_str = request.GET.get("fecha", str(hoy))
    funcionario_id = request.GET.get("funcionario", "")
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    try:
        fecha_reporte = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        fecha_reporte = hoy

    funcionarios = Funcionario.objects.filter(activo=True)

    if not admin_master:
        if empresa_usuario:
            funcionarios = funcionarios.filter(sucursal_rel__empresa=empresa_usuario)
        else:
            funcionarios = funcionarios.none()

    funcionarios = funcionarios.select_related("turno", "sucursal_rel").order_by("apellido", "nombre")

    asistencias_dia = Asistencia.objects.select_related(
        "funcionario",
        "funcionario__turno",
        "funcionario__sucursal_rel",
    ).filter(fecha=fecha_reporte)

    if not admin_master:
        if empresa_usuario:
            asistencias_dia = asistencias_dia.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            asistencias_dia = asistencias_dia.none()

    if funcionario_id:
        funcionarios = funcionarios.filter(id=funcionario_id)
        asistencias_dia = asistencias_dia.filter(funcionario_id=funcionario_id)

    asistencias_dia = asistencias_dia.order_by("funcionario__apellido", "funcionario__nombre")

    funcionarios_con_turno = funcionarios.filter(turno__isnull=False)

    ids_con_asistencia = list(
        asistencias_dia.values_list("funcionario_id", flat=True).distinct()
    )

    permisos_dia = PermisoLicencia.objects.select_related(
        "funcionario",
        "funcionario__turno",
        "funcionario__sucursal_rel",
    ).filter(
        funcionario__in=funcionarios,
        estado=PermisoLicencia.Estados.APROBADO,
        fecha_desde=fecha_reporte,
    )

    vacaciones_dia = Vacacion.objects.select_related(
        "funcionario",
        "funcionario__turno",
        "funcionario__sucursal_rel",
    ).filter(
        funcionario__in=funcionarios,
        estado=Vacacion.Estados.APROBADO,
        fecha_desde=fecha_reporte,
    )

    ids_justificados = set(permisos_dia.values_list("funcionario_id", flat=True))
    ids_justificados.update(vacaciones_dia.values_list("funcionario_id", flat=True))

    ahora = timezone.localtime()
    ausentes_ids_inteligentes = []

    for funcionario in funcionarios_con_turno:
        if funcionario.id in ids_con_asistencia or funcionario.id in ids_justificados:
            continue

        if funcionario_tiene_dia_libre(funcionario, fecha_reporte):
            continue

        if not funcionario.turno or not funcionario.turno.hora_entrada:
            continue

        entrada_programada = timezone.make_aware(
            datetime.combine(fecha_reporte, funcionario.turno.hora_entrada)
        )

        entrada_limite = entrada_programada + timezone.timedelta(
            minutes=funcionario.turno.tolerancia_minutos or 0
        )

        if fecha_reporte < hoy:
            ausentes_ids_inteligentes.append(funcionario.id)
        elif fecha_reporte == hoy and ahora >= entrada_limite:
            ausentes_ids_inteligentes.append(funcionario.id)
        elif fecha_reporte > hoy:
            pass

    ausentes_dia = funcionarios_con_turno.filter(id__in=ausentes_ids_inteligentes)

    llegadas_tarde = asistencias_dia.filter(
        hora_entrada__isnull=False,
        llego_tarde=True
    )

    presentes_en_horario = asistencias_dia.filter(
        hora_entrada__isnull=False,
        llego_tarde=False
    )

    sin_salida = asistencias_dia.filter(
        hora_entrada__isnull=False,
        hora_salida__isnull=True
    )

    permisos_licencias_dia = []
    for item in permisos_dia:
        permisos_licencias_dia.append({
            "tipo": "Permiso / Licencia",
            "funcionario": item.funcionario,
            "obj": item,
        })

    for item in vacaciones_dia:
        permisos_licencias_dia.append({
            "tipo": "Vacación",
            "funcionario": item.funcionario,
            "obj": item,
        })

    permisos_reporte_dia = permisos_dia
    vacaciones_reporte_dia = vacaciones_dia    

    presentes_dia = asistencias_dia.filter(hora_entrada__isnull=False).count()
    tardanzas_dia = llegadas_tarde.count()
    salidas_dia = asistencias_dia.filter(hora_salida__isnull=False).count()
    ausencias_dia = ausentes_dia.count()
    justificados_dia = len({item["funcionario"].id for item in permisos_licencias_dia})
    sin_salida_dia = sin_salida.count()
    programados_dia = funcionarios_con_turno.count()
    en_horario_dia = presentes_en_horario.count()

    requieren_atencion_hoy = tardanzas_dia + ausencias_dia + sin_salida_dia

    porcentaje_asistencia = 0
    if programados_dia > 0:
        porcentaje_asistencia = round((presentes_dia / programados_dia) * 100, 1)

    porcentaje_cumplimiento = 0
    if programados_dia > 0:
        porcentaje_cumplimiento = round((en_horario_dia / programados_dia) * 100, 1)

    resumen_semaforo = {
        "verde": en_horario_dia,
        "amarillo": tardanzas_dia,
        "rojo": ausencias_dia,
        "naranja": sin_salida_dia,
        "azul": justificados_dia,
    }

    resultados_mensuales = []
    funcionarios_para_mes = funcionarios

    dias_mes = monthrange(anio, mes)[1]
    total_dias_laborales_estimados = sum(
        1 for dia in range(1, dias_mes + 1)
        if date(anio, mes, dia).weekday() != 6
    )

    for funcionario in funcionarios_para_mes:
        asistencias_mes = Asistencia.objects.filter(
            funcionario=funcionario,
            fecha__year=anio,
            fecha__month=mes,
            hora_entrada__isnull=False,
        )

        asistencias_count = asistencias_mes.count()
        atrasos_count = asistencias_mes.filter(llego_tarde=True).count()

        dias_libres_mes = contar_dias_libres_mes(funcionario, mes, anio)
        total_dias_laborales_reales = max(total_dias_laborales_estimados - dias_libres_mes, 0)
        ausencias_estimadas = max(total_dias_laborales_reales - asistencias_count, 0)

        permisos_aprobados = PermisoLicencia.objects.filter(
            funcionario=funcionario,
            estado=PermisoLicencia.Estados.APROBADO,
            fecha_desde__year=anio,
            fecha_desde__month=mes,
        ).count()

        vacaciones_aprobadas = Vacacion.objects.filter(
            funcionario=funcionario,
            estado=Vacacion.Estados.APROBADO,
            fecha_desde__year=anio,
            fecha_desde__month=mes,
        ).count()

        ausencias_no_justificadas = max(
            ausencias_estimadas - (permisos_aprobados + vacaciones_aprobadas),
            0
        )

        icl = 100 - (atrasos_count * 2) - (ausencias_no_justificadas * 5)
        icl = max(0, min(100, icl))

        resultados_mensuales.append({
            "funcionario": funcionario,
            "asistencias": asistencias_count,
            "atrasos": atrasos_count,
            "ausencias": ausencias_estimadas,
            "permisos_aprobados": permisos_aprobados,
            "vacaciones_aprobadas": vacaciones_aprobadas,
            "dias_libres_mes": dias_libres_mes,
            "icl": icl,
            "salario_bruto": funcionario.salario_bruto,
            "deudas_mes": funcionario.descuento_deudas_mes,
            "salario_neto": funcionario.salario_neto_estimado,
        })

    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]
    anios = list(range(hoy.year - 2, hoy.year + 2))

    dias_libres_reporte_dia = []

    for funcionario in funcionarios:
        if funcionario_tiene_dia_libre(funcionario, fecha_reporte):
            dias_libres_reporte_dia.append(funcionario)

    return render(request, "core/reportes.html", {
        "fecha_reporte": fecha_reporte,
        "funcionarios": funcionarios,
        "funcionario_id": funcionario_id,
        "asistencias_dia": asistencias_dia,
        "presentes_dia": presentes_dia,
        "tardanzas_dia": tardanzas_dia,
        "salidas_dia": salidas_dia,
        "ausencias_dia": ausencias_dia,
        "justificados_dia": justificados_dia,
        "sin_salida_dia": sin_salida_dia,
        "programados_dia": programados_dia,
        "en_horario_dia": en_horario_dia,
        "porcentaje_asistencia": porcentaje_asistencia,
        "porcentaje_cumplimiento": porcentaje_cumplimiento,
        "requieren_atencion_hoy": requieren_atencion_hoy,
        "resumen_semaforo": resumen_semaforo,
        "llegadas_tarde": llegadas_tarde,
        "ausentes_dia": ausentes_dia,
        "permisos_licencias_dia": permisos_licencias_dia,
        "permisos_reporte_dia": permisos_reporte_dia,
        "vacaciones_reporte_dia": vacaciones_reporte_dia,
        "dias_libres_reporte_dia": dias_libres_reporte_dia,
        "sin_salida": sin_salida,
        "presentes_en_horario": presentes_en_horario,
        "mes": mes,
        "anio": anio,
        "meses": meses,
        "anios": anios,
        "resultados_mensuales": resultados_mensuales,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def historial_lista(request):
    permiso = validar_permiso_o_redirigir(request, "historial", "puede_ver")
    if permiso:
        return permiso

    if not es_admin_master(request.user):
        messages.error(request, "El historial general solo está disponible para el administrador master.")
        return redirect("dashboard")

    q = request.GET.get("q", "").strip()
    historial = HistorialAccion.objects.select_related("usuario").all()

    if q:
        historial = historial.filter(
            Q(modulo__icontains=q) |
            Q(accion__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(usuario__username__icontains=q) |
            Q(usuario__first_name__icontains=q) |
            Q(usuario__last_name__icontains=q)
        )

    return render(request, "core/historial_lista.html", {
        "historial": historial[:300],
        "q": q,
    })

@login_required
def nomina_lista(request):
    permiso = validar_permiso_o_redirigir(request, "nomina", "puede_ver")
    if permiso:
        return permiso

    hoy = timezone.localdate()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))
    estado = request.GET.get("estado", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    empresa_cierre = None if admin_master else empresa_usuario

    cierre_nomina = CierreNomina.objects.filter(
        mes=mes,
        anio=anio,
        empresa=empresa_cierre,
        cerrado=True
    ).first()

    if request.method == "POST":
        permiso_post = validar_permiso_o_redirigir(request, "nomina", "puede_crear")
        if permiso_post:
            return permiso_post

        funcionarios = Funcionario.objects.filter(activo=True)

        if not admin_master:
            if empresa_usuario:
                funcionarios = funcionarios.filter(sucursal_rel__empresa=empresa_usuario)
            else:
                funcionarios = funcionarios.none()

        if cierre_nomina:
            messages.error(request, "Esta nómina ya está cerrada. Debes reabrirla antes de recalcular.")
            return redirect(f"/nomina/?mes={mes}&anio={anio}")        

        funcionarios = funcionarios.order_by("apellido", "nombre")

        for funcionario in funcionarios:
            generar_nomina_funcionario(funcionario, mes, anio)

        registrar_historial(
            request,
            "Nómina",
            "Generar/Recalcular",
            f"Se generó o recalculó la nómina del período {mes:02d}/{anio}."
        )
        messages.success(request, f"Nómina de {mes:02d}/{anio} generada correctamente.")
        return redirect(f"/nomina/?mes={mes}&anio={anio}")

    nominas = NominaMensual.objects.select_related(
        "funcionario",
        "funcionario__sucursal_rel",
        "funcionario__sucursal_rel__empresa"
    ).filter(
        mes=mes,
        anio=anio
    )

    if not admin_master:
        if empresa_usuario:
            nominas = nominas.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            nominas = nominas.none()

    if not nominas.exists():
        funcionarios = Funcionario.objects.filter(activo=True)

        if not admin_master:
            if empresa_usuario:
                funcionarios = funcionarios.filter(sucursal_rel__empresa=empresa_usuario)
            else:
                funcionarios = funcionarios.none()

        funcionarios = funcionarios.order_by("apellido", "nombre")

        for funcionario in funcionarios:
            generar_nomina_funcionario(funcionario, mes, anio)

        nominas = NominaMensual.objects.select_related(
            "funcionario",
            "funcionario__sucursal_rel",
            "funcionario__sucursal_rel__empresa"
        ).filter(
            mes=mes,
            anio=anio
        )

        if not admin_master:
            if empresa_usuario:
                nominas = nominas.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
            else:
                nominas = nominas.none()

    if estado:
        nominas = nominas.filter(estado_pago=estado)

    nominas = nominas.order_by("funcionario__apellido", "funcionario__nombre")

    total_bruto = nominas.aggregate(total=Sum("salario_bruto"))["total"] or Decimal("0.00")
    total_deudas = nominas.aggregate(total=Sum("descuento_deudas"))["total"] or Decimal("0.00")
    total_neto = nominas.aggregate(total=Sum("salario_neto"))["total"] or Decimal("0.00")
    total_pagados = nominas.filter(estado_pago=NominaMensual.EstadosPago.PAGADO).count()
    total_pendientes = nominas.filter(estado_pago=NominaMensual.EstadosPago.PENDIENTE).count()

    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]
    anios = list(range(hoy.year - 2, hoy.year + 2))

    if admin_master:
        sucursales = Sucursal.objects.filter(activo=True).order_by("empresa__nombre", "nombre")
    else:
        sucursales = Sucursal.objects.filter(
            activo=True,
            empresa=empresa_usuario
        ).order_by("nombre") if empresa_usuario else Sucursal.objects.none()

    return render(request, "core/nomina_lista.html", {
        "nominas": nominas,
        "mes": mes,
        "anio": anio,
        "estado": estado,
        "meses": meses,
        "anios": anios,
        "sucursales": sucursales,
        "cierre_nomina": cierre_nomina,
        "total_bruto": total_bruto,
        "total_deudas": total_deudas,
        "total_neto": total_neto,
        "total_pagados": total_pagados,
        "total_pendientes": total_pendientes,
        "estados_pago": NominaMensual.EstadosPago.choices,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def nomina_toggle_pagado(request, pk):
    permiso = validar_permiso_o_redirigir(request, "nomina", "puede_pagar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    nomina = get_object_or_404(
        NominaMensual.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not nomina.funcionario.sucursal_rel or nomina.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes cambiar nóminas de otra empresa.")
            return redirect(f"/nomina/?mes={nomina.mes}&anio={nomina.anio}")

    if nomina.estado_pago == NominaMensual.EstadosPago.PAGADO:
        nomina.estado_pago = NominaMensual.EstadosPago.PENDIENTE
        nomina.fecha_pago = None
        accion = "revirtió a pendiente"
    else:
        nomina.estado_pago = NominaMensual.EstadosPago.PAGADO
        nomina.fecha_pago = timezone.localdate()
        accion = "marcó como pagada"

    nomina.save()

    registrar_historial(
        request,
        "Nómina",
        "Cambio de estado",
        f"Se {accion} la nómina de {nomina.funcionario.nombre_completo} del período {nomina.mes:02d}/{nomina.anio}."
    )
    messages.success(request, "Estado de nómina actualizado correctamente.")
    return redirect(f"/nomina/?mes={nomina.mes}&anio={nomina.anio}")

def _gs(valor):
    return f"Gs. {Decimal(valor or 0):,.0f}".replace(",", ".")

@login_required
def nomina_cerrar_periodo(request):
    permiso = validar_permiso_o_redirigir(request, "nomina", "puede_pagar")
    if permiso:
        return permiso

    hoy = timezone.localdate()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    empresa_cierre = None if admin_master else empresa_usuario

    cierre, creado = CierreNomina.objects.get_or_create(
        mes=mes,
        anio=anio,
        empresa=empresa_cierre,
        defaults={
            "cerrado": True,
            "cerrado_por": request.user,
            "cerrado_en": timezone.now(),
            "observacion": "Cierre manual de nómina.",
        }
    )

    if not creado:
        cierre.cerrado = True
        cierre.cerrado_por = request.user
        cierre.cerrado_en = timezone.now()
        cierre.save()

    registrar_historial(
        request,
        "Nómina",
        "Cerrar período",
        f"Se cerró la nómina del período {mes:02d}/{anio}."
    )

    messages.success(request, f"Nómina {mes:02d}/{anio} cerrada correctamente.")
    return redirect(f"/nomina/?mes={mes}&anio={anio}")


@login_required
def nomina_reabrir_periodo(request):
    permiso = validar_permiso_o_redirigir(request, "nomina", "puede_pagar")
    if permiso:
        return permiso

    hoy = timezone.localdate()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    empresa_cierre = None if admin_master else empresa_usuario

    cierre = CierreNomina.objects.filter(
        mes=mes,
        anio=anio,
        empresa=empresa_cierre,
        cerrado=True
    ).first()

    if cierre:
        cierre.cerrado = False
        cierre.save()

        registrar_historial(
            request,
            "Nómina",
            "Reabrir período",
            f"Se reabrió la nómina del período {mes:02d}/{anio}."
        )

        messages.success(request, f"Nómina {mes:02d}/{anio} reabierta correctamente.")
    else:
        messages.warning(request, "No existe un cierre activo para este período.")

    return redirect(f"/nomina/?mes={mes}&anio={anio}")

def _nomina_permitida(request, nomina):
    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if admin_master:
        return True

    return (
        empresa_usuario
        and nomina.funcionario.sucursal_rel
        and nomina.funcionario.sucursal_rel.empresa == empresa_usuario
    )


@login_required
def nomina_extracto_pdf(request, pk):
    permiso = validar_permiso_o_redirigir(request, "nomina", "puede_ver")
    if permiso:
        return permiso

    nomina = get_object_or_404(
        NominaMensual.objects.select_related(
            "funcionario",
            "funcionario__sucursal_rel",
            "funcionario__sucursal_rel__empresa"
        ),
        pk=pk
    )

    if not _nomina_permitida(request, nomina):
        messages.error(request, "No puedes exportar nóminas de otra empresa.")
        return redirect("nomina_lista")

    funcionario = nomina.funcionario
    config = ConfiguracionGeneral.obtener()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloNomina",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    ))

    elementos = []

    elementos.append(Paragraph(config.nombre_sistema or "ClockIn", styles["TituloNomina"]))
    elementos.append(Paragraph("EXTRACTO DE NÓMINA INDIVIDUAL", styles["TituloNomina"]))
    elementos.append(Spacer(1, 8))

    datos = [
        ["Funcionario", funcionario.nombre_completo],
        ["Cédula", funcionario.cedula],
        ["Empresa", funcionario.empresa_mostrar],
        ["Sucursal", funcionario.sucursal_mostrar],
        ["Cargo", funcionario.cargo or "-"],
        ["Período", f"{nomina.mes:02d}/{nomina.anio}"],
        ["Estado", nomina.get_estado_pago_display()],
        ["Fecha de pago", nomina.fecha_pago.strftime("%d/%m/%Y") if nomina.fecha_pago else "-"],
        ["Modalidad de cobro", nomina.modalidad_cobro or "-"],
        ["Banco", nomina.banco or "-"],
        ["Cuenta", f"{nomina.tipo_cuenta or '-'} / {nomina.numero_cuenta or '-'}"],
    ]

    tabla_datos = Table(datos, colWidths=[55 * mm, 105 * mm])
    tabla_datos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1d4ed8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 12))

    tabla_liquidacion = Table([
        ["Concepto", "Monto"],
        ["Salario base", _gs(nomina.salario_base)],
        ["Bono base configurado", _gs(nomina.bono_base)],
        ["Bono pagado según ICL", _gs(nomina.bono_icl)],
        ["Salario bruto", _gs(nomina.salario_bruto)],
        ["IPS", f"- {_gs(nomina.descuento_ips)}"],
        ["Deudas", f"- {_gs(nomina.descuento_deudas)}"],
        ["NETO FINAL A COBRAR", _gs(nomina.salario_neto)],
    ], colWidths=[110 * mm, 50 * mm])

    tabla_liquidacion.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcfce7")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#166534")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_liquidacion)
    elementos.append(Spacer(1, 26))

    firmas = Table([
        ["_______________________________", "_______________________________"],
        ["Firma responsable", "Firma funcionario"],
    ], colWidths=[80 * mm, 80 * mm])

    firmas.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elementos.append(firmas)

    doc.build(elementos)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="extracto_nomina_{funcionario.cedula}_{nomina.mes:02d}_{nomina.anio}.pdf"'
    response.write(pdf)
    return response


@login_required
def nomina_sucursal_pdf(request):
    permiso = validar_permiso_o_redirigir(request, "nomina", "puede_ver")
    if permiso:
        return permiso

    hoy = timezone.localdate()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))
    sucursal_id = request.GET.get("sucursal", "").strip()

    if not sucursal_id:
        messages.error(request, "Debes seleccionar una sucursal para generar el extracto general.")
        return redirect(f"/nomina/?mes={mes}&anio={anio}")

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    sucursal = get_object_or_404(Sucursal.objects.select_related("empresa"), pk=sucursal_id)

    if not admin_master and sucursal.empresa != empresa_usuario:
        messages.error(request, "No puedes exportar nóminas de otra empresa.")
        return redirect("nomina_lista")

    nominas = NominaMensual.objects.select_related(
        "funcionario",
        "funcionario__sucursal_rel",
        "funcionario__sucursal_rel__empresa"
    ).filter(
        mes=mes,
        anio=anio,
        funcionario__sucursal_rel=sucursal
    ).order_by("funcionario__apellido", "funcionario__nombre")

    total_bruto = nominas.aggregate(total=Sum("salario_bruto"))["total"] or Decimal("0.00")
    total_ips = nominas.aggregate(total=Sum("descuento_ips"))["total"] or Decimal("0.00")
    total_deudas = nominas.aggregate(total=Sum("descuento_deudas"))["total"] or Decimal("0.00")
    total_neto = nominas.aggregate(total=Sum("salario_neto"))["total"] or Decimal("0.00")
    total_bono = nominas.aggregate(total=Sum("bono_icl"))["total"] or Decimal("0.00")

    config = ConfiguracionGeneral.obtener()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloSucursal",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    ))

    elementos = []

    elementos.append(Paragraph(config.nombre_sistema or "ClockIn", styles["TituloSucursal"]))
    elementos.append(Paragraph("EXTRACTO GENERAL DE NÓMINA POR SUCURSAL", styles["TituloSucursal"]))
    elementos.append(Spacer(1, 8))

    resumen = Table([
        ["Empresa", sucursal.empresa.nombre],
        ["Sucursal", sucursal.nombre],
        ["Período", f"{mes:02d}/{anio}"],
        ["Cantidad de funcionarios", str(nominas.count())],
        ["Total bruto", _gs(total_bruto)],
        ["Total bono ICL", _gs(total_bono)],
        ["Total IPS", _gs(total_ips)],
        ["Total deudas", _gs(total_deudas)],
        ["Total neto general", _gs(total_neto)],
    ], colWidths=[65 * mm, 105 * mm])

    resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1d4ed8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    elementos.append(resumen)
    elementos.append(Spacer(1, 12))

    data = [["Funcionario", "CI", "Bruto", "IPS", "Deudas", "Neto", "Estado"]]

    for n in nominas:
        data.append([
            n.funcionario.nombre_completo,
            n.funcionario.cedula,
            _gs(n.salario_bruto),
            _gs(n.descuento_ips),
            _gs(n.descuento_deudas),
            _gs(n.salario_neto),
            n.get_estado_pago_display(),
        ])

    tabla = Table(data, colWidths=[45 * mm, 22 * mm, 24 * mm, 22 * mm, 24 * mm, 26 * mm, 24 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("ALIGN", (2, 1), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elementos.append(tabla)

    doc.build(elementos)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="nomina_sucursal_{sucursal.id}_{mes:02d}_{anio}.pdf"'
    response.write(pdf)
    return response

@login_required
def configuracion_general(request):
    permiso = validar_permiso_o_redirigir(request, "configuracion", "puede_ver")
    if permiso:
        return permiso

    config = ConfiguracionGeneral.obtener()

    mapa_hex_a_tema = {
        "#2563eb": ConfiguracionGeneral.TEMA_AZUL,
        "#16a34a": ConfiguracionGeneral.TEMA_VERDE,
        "#dc2626": ConfiguracionGeneral.TEMA_ROJO,
        "#ea580c": ConfiguracionGeneral.TEMA_NARANJA,
        "#7c3aed": ConfiguracionGeneral.TEMA_MORADO,
        "#0891b2": ConfiguracionGeneral.TEMA_TURQUESA,
        "#475569": ConfiguracionGeneral.TEMA_GRIS,
    }

    valores_validos = {item[0] for item in ConfiguracionGeneral.TEMAS_CHOICES}

    if config.color_primario in mapa_hex_a_tema:
        config.color_primario = mapa_hex_a_tema[config.color_primario]
        config.save(update_fields=["color_primario"])
    elif config.color_primario not in valores_validos:
        config.color_primario = ConfiguracionGeneral.TEMA_AZUL
        config.save(update_fields=["color_primario"])

    if request.method == "POST":
        permiso_post = validar_permiso_o_redirigir(request, "configuracion", "puede_editar")
        if permiso_post:
            return permiso_post

        post_data = request.POST.copy()

        for campo in [
            "bancos_personalizados",
            "cargos_personalizados",
            "sectores_personalizados",
        ]:
            valor = post_data.get(campo, "")
            items = []
            for linea in valor.splitlines():
                item = linea.strip()
                if item and item not in items:
                    items.append(item)
            post_data[campo] = "\n".join(items)

        form = ConfiguracionGeneralForm(post_data, instance=config)

        if form.is_valid():
            config = form.save()

            Funcionario.objects.all().update(
                salario_base=config.salario_base_default,
                porcentaje_limite_deuda=config.porcentaje_limite_deuda_default,
            )

            registrar_historial(
                request,
                "Configuraciones",
                "Editar",
                f"Configuración PRO Plus actualizada. "
                f"Salario base: {config.salario_base_default}, "
                f"Límite deuda: {config.porcentaje_limite_deuda_default}%, "
                f"Tolerancia: {config.tolerancia_minutos_default} min, "
                f"Lectura biométrica: {config.biometrico_segundos_lectura}s, "
                f"Tema: {config.color_primario}."
            )

            messages.success(request, "Configuración PRO Plus actualizada correctamente.")
            return redirect("configuracion_general")

        messages.error(request, "No se pudo guardar la configuración. Revisa los campos marcados.")
        print(form.errors)

    else:
        form = ConfiguracionGeneralForm(instance=config)

    return render(request, "core/configuracion_general.html", {
        "form": form,
        "config": config,
    })

@login_required
def liquidaciones_lista(request):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_ver")
    if permiso:
        return permiso

    q = request.GET.get("q", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    liquidaciones = Liquidacion.objects.select_related(
        "funcionario",
        "funcionario__sucursal_rel",
        "funcionario__sucursal_rel__empresa"
    ).all()

    if not admin_master:
        if empresa_usuario:
            liquidaciones = liquidaciones.filter(funcionario__sucursal_rel__empresa=empresa_usuario)
        else:
            liquidaciones = liquidaciones.none()

    if q:
        liquidaciones = liquidaciones.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q) |
            Q(tipo_salida__icontains=q) |
            Q(estado__icontains=q)
        )

    return render(request, "core/liquidaciones_lista.html", {
        "liquidaciones": liquidaciones,
        "q": q,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def liquidacion_nueva(request):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_crear")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    resumen = None

    if request.method == "POST":
        form = LiquidacionForm(request.POST)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

        if form.is_valid():
            liquidacion = form.save(commit=False)

            if not admin_master:
                if not liquidacion.funcionario.sucursal_rel or liquidacion.funcionario.sucursal_rel.empresa != empresa_usuario:
                    messages.error(request, "No puedes crear liquidaciones para otra empresa.")
                    return redirect("liquidaciones_lista")

            resumen = calcular_liquidacion_funcionario(
                funcionario=liquidacion.funcionario,
                tipo_salida=liquidacion.tipo_salida,
                fecha_salida=liquidacion.fecha_salida,
                dias_trabajados_pendientes=liquidacion.dias_trabajados_pendientes,
                vacaciones_causadas_pendientes_dias=liquidacion.vacaciones_causadas_pendientes_dias,
                preaviso_dias_otorgados=liquidacion.preaviso_dias_otorgados,
                preaviso_cumplido=liquidacion.preaviso_cumplido,
                descontar_preaviso=liquidacion.descontar_preaviso,
                otros_descuentos=liquidacion.otros_descuentos,
            )

            for campo, valor in resumen.items():
                setattr(liquidacion, campo, valor)

            if not liquidacion.fecha_calculo:
                liquidacion.fecha_calculo = timezone.localdate()

            liquidacion.save()

            registrar_historial(
                request,
                "Liquidaciones",
                "Crear",
                f"Se creó liquidación para {liquidacion.funcionario.nombre_completo} - {liquidacion.get_tipo_salida_display()}."
            )

            messages.success(request, "Liquidación generada correctamente.")
            return redirect("liquidacion_detalle", pk=liquidacion.pk)
    else:
        form = LiquidacionForm(initial={"fecha_calculo": timezone.localdate()})

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")

    return render(request, "core/liquidacion_form.html", {
        "form": form,
        "resumen": resumen,
        "titulo_form": "Nueva liquidación",
    })


@login_required
def liquidacion_preview(request):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_crear")
    if permiso:
        return JsonResponse({"ok": False, "error": "Sin permiso."}, status=403)

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    funcionario_id = request.GET.get("funcionario")
    tipo_salida = request.GET.get("tipo_salida")
    fecha_salida = request.GET.get("fecha_salida")

    dias_trabajados_pendientes = request.GET.get("dias_trabajados_pendientes")
    vacaciones_causadas_pendientes_dias = request.GET.get("vacaciones_causadas_pendientes_dias")
    preaviso_dias_otorgados = request.GET.get("preaviso_dias_otorgados", "0")
    preaviso_cumplido = request.GET.get("preaviso_cumplido") == "true"
    descontar_preaviso = request.GET.get("descontar_preaviso") == "true"
    otros_descuentos = request.GET.get("otros_descuentos", "0")

    if not funcionario_id or not tipo_salida or not fecha_salida:
        return JsonResponse({"ok": False, "error": "Faltan datos para calcular."})

    try:
        funcionario = Funcionario.objects.select_related("sucursal_rel", "sucursal_rel__empresa").get(
            pk=funcionario_id,
            activo=True
        )
    except Funcionario.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Funcionario no encontrado."})

    if not admin_master:
        if not funcionario.sucursal_rel or funcionario.sucursal_rel.empresa != empresa_usuario:
            return JsonResponse({"ok": False, "error": "No puedes calcular liquidación para otra empresa."}, status=403)

    try:
        fecha_salida_obj = datetime.strptime(fecha_salida, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"ok": False, "error": "Fecha de salida inválida."})

    try:
        if dias_trabajados_pendientes in [None, ""]:
            dias_trabajados_pendientes = None
        else:
            dias_trabajados_pendientes = int(dias_trabajados_pendientes)

        if vacaciones_causadas_pendientes_dias in [None, ""]:
            vacaciones_causadas_pendientes_dias = None
        else:
            vacaciones_causadas_pendientes_dias = int(vacaciones_causadas_pendientes_dias)

        preaviso_dias_otorgados = int(preaviso_dias_otorgados or 0)
        otros_descuentos = Decimal(otros_descuentos or 0)
    except (ValueError, InvalidOperation):
        return JsonResponse({"ok": False, "error": "Hay valores numéricos inválidos."})

    resumen = calcular_liquidacion_funcionario(
        funcionario=funcionario,
        tipo_salida=tipo_salida,
        fecha_salida=fecha_salida_obj,
        dias_trabajados_pendientes=dias_trabajados_pendientes,
        vacaciones_causadas_pendientes_dias=vacaciones_causadas_pendientes_dias,
        preaviso_dias_otorgados=preaviso_dias_otorgados,
        preaviso_cumplido=preaviso_cumplido,
        descontar_preaviso=descontar_preaviso,
        otros_descuentos=otros_descuentos,
    )

    return JsonResponse({
        "ok": True,
        "funcionario": funcionario.nombre_completo,
        "tipo_salida": tipo_salida,
        "antiguedad": {
            "anios": resumen["antiguedad_anios"],
            "meses": resumen["antiguedad_meses"],
            "dias": resumen["antiguedad_dias"],
        },
        "salario_base_snapshot": str(resumen["salario_base_snapshot"]),
        "bono_base_snapshot": str(resumen["bono_base_snapshot"]),
        "dias_trabajados_pendientes": resumen["dias_trabajados_pendientes"],
        "salario_pendiente_monto": str(resumen["salario_pendiente_monto"]),
        "vacaciones_causadas_pendientes_dias": resumen["vacaciones_causadas_pendientes_dias"],
        "vacaciones_causadas_monto": str(resumen["vacaciones_causadas_monto"]),
        "vacaciones_proporcionales_dias": resumen["vacaciones_proporcionales_dias"],
        "vacaciones_proporcionales_monto": str(resumen["vacaciones_proporcionales_monto"]),
        "aguinaldo_proporcional_monto": str(resumen["aguinaldo_proporcional_monto"]),
        "preaviso_dias_corresponde": resumen["preaviso_dias_corresponde"],
        "preaviso_dias_otorgados": resumen["preaviso_dias_otorgados"],
        "preaviso_cumplido": resumen["preaviso_cumplido"],
        "preaviso_monto": str(resumen["preaviso_monto"]),
        "indemnizacion_dias": resumen["indemnizacion_dias"],
        "indemnizacion_monto": str(resumen["indemnizacion_monto"]),
        "ips_monto": str(resumen["ips_monto"]),
        "deudas_monto": str(resumen["deudas_monto"]),
        "otros_descuentos": str(resumen["otros_descuentos"]),
        "total_haberes": str(resumen["total_haberes"]),
        "total_descuentos": str(resumen["total_descuentos"]),
        "total_liquidacion": str(resumen["total_liquidacion"]),
        "requiere_revision_juridica": resumen["requiere_revision_juridica"],
        "alerta_revision": resumen["alerta_revision"],
    })


@login_required
def liquidacion_detalle(request, pk):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_ver")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    liquidacion = get_object_or_404(
        Liquidacion.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not liquidacion.funcionario.sucursal_rel or liquidacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes ver liquidaciones de otra empresa.")
            return redirect("liquidaciones_lista")

    return render(request, "core/liquidacion_detalle.html", {
        "liquidacion": liquidacion,
    })


@login_required
def liquidacion_confirmar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_confirmar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    liquidacion = get_object_or_404(
        Liquidacion.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not liquidacion.funcionario.sucursal_rel or liquidacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes confirmar liquidaciones de otra empresa.")
            return redirect("liquidaciones_lista")

    if liquidacion.estado == Liquidacion.Estados.ANULADA:
        messages.error(request, "No puedes confirmar una liquidación anulada.")
        return redirect("liquidacion_detalle", pk=pk)

    liquidacion.estado = Liquidacion.Estados.CONFIRMADA
    liquidacion.save(update_fields=["estado", "actualizado_en"])

    registrar_historial(
        request,
        "Liquidaciones",
        "Confirmar",
        f"Se confirmó la liquidación de {liquidacion.funcionario.nombre_completo}."
    )

    messages.success(request, "Liquidación confirmada correctamente.")
    return redirect("liquidacion_detalle", pk=pk)


@login_required
def liquidacion_marcar_pagada(request, pk):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_pagar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    liquidacion = get_object_or_404(
        Liquidacion.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not liquidacion.funcionario.sucursal_rel or liquidacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes operar liquidaciones de otra empresa.")
            return redirect("liquidaciones_lista")

    if liquidacion.estado == Liquidacion.Estados.ANULADA:
        messages.error(request, "No puedes marcar como pagada una liquidación anulada.")
        return redirect("liquidacion_detalle", pk=pk)

    liquidacion.estado = Liquidacion.Estados.PAGADA
    liquidacion.save(update_fields=["estado", "actualizado_en"])

    registrar_historial(
        request,
        "Liquidaciones",
        "Pagar",
        f"Se marcó como pagada la liquidación de {liquidacion.funcionario.nombre_completo}."
    )

    messages.success(request, "Liquidación marcada como pagada.")
    return redirect("liquidacion_detalle", pk=pk)


@login_required
def liquidacion_anular(request, pk):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_anular")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    liquidacion = get_object_or_404(
        Liquidacion.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not liquidacion.funcionario.sucursal_rel or liquidacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes operar liquidaciones de otra empresa.")
            return redirect("liquidaciones_lista")

    if liquidacion.estado == Liquidacion.Estados.PAGADA:
        messages.error(request, "No puedes anular una liquidación ya pagada.")
        return redirect("liquidacion_detalle", pk=pk)

    liquidacion.estado = Liquidacion.Estados.ANULADA
    liquidacion.save(update_fields=["estado", "actualizado_en"])

    registrar_historial(
        request,
        "Liquidaciones",
        "Anular",
        f"Se anuló la liquidación de {liquidacion.funcionario.nombre_completo}."
    )

    messages.success(request, "Liquidación anulada correctamente.")
    return redirect("liquidacion_detalle", pk=pk)


@login_required
def liquidacion_pdf(request, pk):
    permiso = validar_permiso_o_redirigir(request, "liquidacion", "puede_ver")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    liquidacion = get_object_or_404(
        Liquidacion.objects.select_related("funcionario", "funcionario__sucursal_rel", "funcionario__sucursal_rel__empresa"),
        pk=pk
    )

    if not admin_master:
        if not liquidacion.funcionario.sucursal_rel or liquidacion.funcionario.sucursal_rel.empresa != empresa_usuario:
            messages.error(request, "No puedes operar liquidaciones de otra empresa.")
            return redirect("liquidaciones_lista")

    funcionario = liquidacion.funcionario
    config = ConfiguracionGeneral.obtener()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloClockIn",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SubtituloClockIn",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="SeccionClockIn",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#1d4ed8"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="TextoClockIn",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#111827"),
    ))
    styles.add(ParagraphStyle(
        name="TextoBoldClockIn",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#111827"),
    ))

    elementos = []

    nombre_sistema = config.nombre_sistema if config and config.nombre_sistema else "ClockIn"
    subtitulo = config.subtitulo_sistema if config and config.subtitulo_sistema else "Sistema Web RRHH"

    elementos.append(Paragraph(f"{nombre_sistema}", styles["TituloClockIn"]))
    elementos.append(Paragraph(f"{subtitulo}", styles["SubtituloClockIn"]))
    elementos.append(Paragraph("LIQUIDACIÓN FINAL", styles["TituloClockIn"]))
    elementos.append(Spacer(1, 4))

    datos_superiores = [
        ["Funcionario", funcionario.nombre_completo],
        ["Cédula", funcionario.cedula],
        ["Tipo de salida", liquidacion.get_tipo_salida_display()],
        ["Estado", liquidacion.get_estado_display()],
        ["Fecha de salida", liquidacion.fecha_salida.strftime("%d/%m/%Y") if liquidacion.fecha_salida else "-"],
        ["Fecha de cálculo", liquidacion.fecha_calculo.strftime("%d/%m/%Y") if liquidacion.fecha_calculo else "-"],
        ["Antigüedad", f"{liquidacion.antiguedad_anios} año(s), {liquidacion.antiguedad_meses} mes(es), {liquidacion.antiguedad_dias} día(s)"],
    ]

    tabla_datos = Table(datos_superiores, colWidths=[55 * mm, 105 * mm])
    tabla_datos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1d4ed8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("1. HABERES", styles["SeccionClockIn"]))

    tabla_haberes = Table([
        ["Concepto", "Detalle", "Monto"],
        ["Salario pendiente", f"{liquidacion.dias_trabajados_pendientes} día(s)", f"Gs. {liquidacion.salario_pendiente_monto:,.0f}".replace(",", ".")],
        ["Vacaciones causadas pendientes", f"{liquidacion.vacaciones_causadas_pendientes_dias} día(s)", f"Gs. {liquidacion.vacaciones_causadas_monto:,.0f}".replace(",", ".")],
        ["Vacaciones proporcionales", f"{liquidacion.vacaciones_proporcionales_dias} día(s)", f"Gs. {liquidacion.vacaciones_proporcionales_monto:,.0f}".replace(",", ".")],
        ["Aguinaldo proporcional", "-", f"Gs. {liquidacion.aguinaldo_proporcional_monto:,.0f}".replace(",", ".")],
        ["Preaviso", f"{liquidacion.preaviso_dias_corresponde} día(s) corresponde / {liquidacion.preaviso_dias_otorgados} día(s) otorgado(s)", f"Gs. {liquidacion.preaviso_monto:,.0f}".replace(",", ".")],
        ["Indemnización", f"{liquidacion.indemnizacion_dias} día(s)", f"Gs. {liquidacion.indemnizacion_monto:,.0f}".replace(",", ".")],
        ["TOTAL HABERES", "", f"Gs. {liquidacion.total_haberes:,.0f}".replace(",", ".")],
    ], colWidths=[70 * mm, 65 * mm, 25 * mm])

    tabla_haberes.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_haberes)
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("2. DESCUENTOS", styles["SeccionClockIn"]))

    tabla_desc = Table([
        ["Concepto", "Monto"],
        ["IPS", f"Gs. {liquidacion.ips_monto:,.0f}".replace(",", ".")],
        ["Deudas", f"Gs. {liquidacion.deudas_monto:,.0f}".replace(",", ".")],
        ["Otros descuentos", f"Gs. {liquidacion.otros_descuentos:,.0f}".replace(",", ".")],
        ["TOTAL DESCUENTOS", f"Gs. {liquidacion.total_descuentos:,.0f}".replace(",", ".")],
    ], colWidths=[135 * mm, 25 * mm])

    tabla_desc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef2f2")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#fecaca")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_desc)
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("3. TOTAL FINAL", styles["SeccionClockIn"]))

    tabla_total = Table([
        ["TOTAL LIQUIDACIÓN", f"Gs. {liquidacion.total_liquidacion:,.0f}".replace(",", ".")]
    ], colWidths=[135 * mm, 25 * mm])

    tabla_total.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#166534")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla_total)
    elementos.append(Spacer(1, 14))

    if liquidacion.motivo_observacion:
        elementos.append(Paragraph("4. OBSERVACIÓN", styles["SeccionClockIn"]))
        elementos.append(Paragraph(liquidacion.motivo_observacion.replace("\n", "<br/>"), styles["TextoClockIn"]))
        elementos.append(Spacer(1, 12))

    if liquidacion.requiere_revision_juridica and liquidacion.alerta_revision:
        elementos.append(Paragraph("5. ALERTA DE REVISIÓN", styles["SeccionClockIn"]))
        elementos.append(Paragraph(liquidacion.alerta_revision, styles["TextoBoldClockIn"]))
        elementos.append(Spacer(1, 12))

    elementos.append(Spacer(1, 22))

    firmas = Table([
        ["_______________________________", "_______________________________"],
        ["Firma del empleador / responsable", "Firma del funcionario"],
        ["", ""],
        ["Aclaración: ____________________", "Aclaración: ____________________"],
    ], colWidths=[80 * mm, 80 * mm])

    firmas.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(firmas)

    doc.build(elementos)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="liquidacion_{funcionario.cedula}_{liquidacion.id}.pdf"'
    response.write(pdf)
    return response


@login_required
def dias_libres_lista(request):
    permiso = validar_permiso_o_redirigir(request, "dias_libres", "puede_ver")
    if permiso:
        return permiso

    empresa_id = request.GET.get("empresa", "").strip()
    sucursal_id = request.GET.get("sucursal", "").strip()
    sector = request.GET.get("sector", "").strip()
    q = request.GET.get("q", "").strip()

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    dias_libres = DiaLibre.objects.select_related(
        "funcionario",
        "empresa",
        "sucursal",
    ).filter(activo=True)

    funcionarios_activos = Funcionario.objects.filter(activo=True).select_related(
        "sucursal_rel",
        "sucursal_rel__empresa"
    )

    if not admin_master:
        if empresa_usuario:
            empresa_id = str(empresa_usuario.id)
            dias_libres = dias_libres.filter(empresa=empresa_usuario)
            funcionarios_activos = funcionarios_activos.filter(sucursal_rel__empresa=empresa_usuario)
        else:
            dias_libres = dias_libres.none()
            funcionarios_activos = funcionarios_activos.none()

    if empresa_id:
        dias_libres = dias_libres.filter(empresa_id=empresa_id)
        funcionarios_activos = funcionarios_activos.filter(sucursal_rel__empresa_id=empresa_id)

    if sucursal_id:
        dias_libres = dias_libres.filter(sucursal_id=sucursal_id)
        funcionarios_activos = funcionarios_activos.filter(sucursal_rel_id=sucursal_id)

    if sector:
        dias_libres = dias_libres.filter(sector=sector)
        funcionarios_activos = funcionarios_activos.filter(sector=sector)

    if q:
        dias_libres = dias_libres.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q) |
            Q(sector__icontains=q)
        )

        funcionarios_activos = funcionarios_activos.filter(
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q) |
            Q(cedula__icontains=q) |
            Q(sector__icontains=q)
        )

    if request.method == "POST":
        permiso_post = validar_permiso_o_redirigir(request, "dias_libres", "puede_crear")
        if permiso_post:
            return permiso_post

        for funcionario in funcionarios_activos:
            dia_valor = request.POST.get(f"dia_libre_{funcionario.id}", "").strip()

            if dia_valor == "":
                continue

            dia_semana = int(dia_valor)

            dia_libre_actual = DiaLibre.objects.filter(
                funcionario=funcionario,
                activo=True
            ).first()

            if dia_libre_actual:
                dia_libre_actual.dia_semana = dia_semana
                dia_libre_actual.empresa = funcionario.empresa
                dia_libre_actual.sucursal = funcionario.sucursal_rel
                dia_libre_actual.sector = funcionario.sector or ""
                dia_libre_actual.fecha_inicio = timezone.localdate()
                dia_libre_actual.save()
            else:
                DiaLibre.objects.create(
                    funcionario=funcionario,
                    empresa=funcionario.empresa,
                    sucursal=funcionario.sucursal_rel,
                    sector=funcionario.sector or "",
                    dia_semana=dia_semana,
                    fecha_inicio=timezone.localdate(),
                    activo=True,
                )

        registrar_historial(
            request,
            "Días Libres",
            "Asignación rápida",
            f"Se actualizaron días libres por sector/sucursal. Sector: {sector or 'Todos'}."
        )

        messages.success(request, "Días libres actualizados correctamente.")
        return redirect(f"/dias-libres/?empresa={empresa_id}&sucursal={sucursal_id}&sector={sector}&q={q}")

    if admin_master:
        empresas = Empresa.objects.filter(activo=True).order_by("nombre")
        sucursales = Sucursal.objects.filter(activo=True).order_by("nombre")
        if empresa_id:
            sucursales = sucursales.filter(empresa_id=empresa_id)
    else:
        empresas = Empresa.objects.filter(id=empresa_usuario.id) if empresa_usuario else Empresa.objects.none()
        sucursales = Sucursal.objects.filter(
            activo=True,
            empresa=empresa_usuario
        ).order_by("nombre") if empresa_usuario else Sucursal.objects.none()

    sectores_qs = Funcionario.objects.filter(activo=True).exclude(sector="")

    if not admin_master and empresa_usuario:
        sectores_qs = sectores_qs.filter(sucursal_rel__empresa=empresa_usuario)

    if empresa_id:
        sectores_qs = sectores_qs.filter(sucursal_rel__empresa_id=empresa_id)

    if sucursal_id:
        sectores_qs = sectores_qs.filter(sucursal_rel_id=sucursal_id)

    sectores = sectores_qs.values_list("sector", flat=True).distinct().order_by("sector")

    total_funcionarios = funcionarios_activos.count()
    total_asignados = DiaLibre.objects.filter(
        activo=True,
        funcionario__in=funcionarios_activos
    ).values("funcionario").distinct().count()
    total_pendientes = max(total_funcionarios - total_asignados, 0)

    funcionarios_rapidos = []

    for funcionario in funcionarios_activos.order_by("apellido", "nombre"):
        dia_actual = DiaLibre.objects.filter(
            funcionario=funcionario,
            activo=True
        ).first()

        funcionarios_rapidos.append({
            "funcionario": funcionario,
            "dia_actual": dia_actual.dia_semana if dia_actual else "",
        })

    return render(request, "core/dias_libres_lista.html", {
        "dias_libres": dias_libres.order_by("sector", "dia_semana", "funcionario__apellido"),
        "funcionarios_rapidos": funcionarios_rapidos,
        "dias_semana_choices": DiaLibre.DiasSemana.choices,
        "empresas": empresas,
        "sucursales": sucursales,
        "sectores": sectores,
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
        "sector": sector,
        "q": q,
        "total_funcionarios": total_funcionarios,
        "total_asignados": total_asignados,
        "total_pendientes": total_pendientes,
        "empresa_usuario": empresa_usuario,
        "es_admin_master": admin_master,
    })


@login_required
def dia_libre_nuevo(request):
    permiso = validar_permiso_o_redirigir(request, "dias_libres", "puede_crear")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    if request.method == "POST":
        form = DiaLibreForm(request.POST)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id)
            form.fields["sucursal"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

        if form.is_valid():
            dia_libre = form.save(commit=False)

            if not admin_master:
                if dia_libre.empresa != empresa_usuario:
                    messages.error(request, "No puedes crear días libres para otra empresa.")
                    return redirect("dias_libres_lista")

            dia_libre.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Días Libres",
                "Crear",
                f"Se asignó día libre {dia_libre.get_dia_semana_display()} a {dia_libre.funcionario.nombre_completo}."
            )
            messages.success(request, "Día libre asignado correctamente.")
            return redirect("dias_libres_lista")
    else:
        form = DiaLibreForm()

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id)
            form.fields["empresa"].initial = empresa_usuario
            form.fields["sucursal"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

    return render(request, "core/dia_libre_form.html", {
        "form": form,
        "titulo_form": "Nuevo día libre",
        "boton_texto": "Guardar día libre",
    })


@login_required
def dia_libre_editar(request, pk):
    permiso = validar_permiso_o_redirigir(request, "dias_libres", "puede_editar")
    if permiso:
        return permiso

    empresa_usuario = obtener_empresa_usuario(request.user)
    admin_master = es_admin_master(request.user)

    dia_libre = get_object_or_404(DiaLibre, pk=pk)

    if not admin_master:
        if dia_libre.empresa != empresa_usuario:
            messages.error(request, "No puedes editar días libres de otra empresa.")
            return redirect("dias_libres_lista")

    if request.method == "POST":
        form = DiaLibreForm(request.POST, instance=dia_libre)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id)
            form.fields["sucursal"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

        if form.is_valid():
            dia_libre_editado = form.save(commit=False)

            if not admin_master:
                if dia_libre_editado.empresa != empresa_usuario:
                    messages.error(request, "No puedes mover días libres a otra empresa.")
                    return redirect("dias_libres_lista")

            dia_libre_editado.save()
            form.save_m2m()

            registrar_historial(
                request,
                "Días Libres",
                "Editar",
                f"Se editó día libre de {dia_libre_editado.funcionario.nombre_completo}."
            )
            messages.success(request, "Día libre actualizado correctamente.")
            return redirect("dias_libres_lista")
    else:
        form = DiaLibreForm(instance=dia_libre)

        if not admin_master and empresa_usuario:
            form.fields["funcionario"].queryset = Funcionario.objects.filter(
                activo=True,
                sucursal_rel__empresa=empresa_usuario
            ).order_by("apellido", "nombre")
            form.fields["empresa"].queryset = Empresa.objects.filter(id=empresa_usuario.id)
            form.fields["sucursal"].queryset = Sucursal.objects.filter(
                activo=True,
                empresa=empresa_usuario
            ).order_by("nombre")

    return render(request, "core/dia_libre_form.html", {
        "form": form,
        "titulo_form": "Editar día libre",
        "boton_texto": "Actualizar día libre",
    })


@login_required
def dia_libre_toggle_activo(request, pk):
    permiso = validar_permiso_o_redirigir(request, "dias_libres", "puede_editar")
    if permiso:
        return permiso

    dia_libre = get_object_or_404(DiaLibre, pk=pk)
    dia_libre.activo = not dia_libre.activo
    dia_libre.save(update_fields=["activo", "actualizado_en"])

    registrar_historial(
        request,
        "Días Libres",
        "Estado",
        f"Se cambió estado de día libre de {dia_libre.funcionario.nombre_completo} a {'Activo' if dia_libre.activo else 'Inactivo'}."
    )

    messages.success(request, "Estado del día libre actualizado correctamente.")
    return redirect("dias_libres_lista")

@login_required
def asistencia_eliminar(request, pk):
    if not es_admin_master(request.user):
        messages.error(request, "Solo el administrador global puede eliminar asistencias.")
        return redirect("asistencia_marcar")

    asistencia = get_object_or_404(
        Asistencia.objects.select_related("funcionario"),
        pk=pk
    )

    funcionario = asistencia.funcionario
    fecha = asistencia.fecha

    if request.method == "POST":
        motivo = request.POST.get("motivo", "").strip()

        if not motivo:
            messages.error(request, "Debes indicar el motivo de eliminación.")
            return redirect("asistencia_marcar")

        registrar_historial(
            request,
            "Asistencia",
            "Eliminar",
            f"Se eliminó asistencia de {funcionario.nombre_completo} "
            f"del día {fecha.strftime('%d/%m/%Y')}. Motivo: {motivo}"
        )

        asistencia.delete()

        messages.success(
            request,
            f"Asistencia de {funcionario.nombre_completo} eliminada correctamente."
        )
        return redirect("asistencia_marcar")

    return render(request, "core/asistencia_eliminar.html", {
        "asistencia": asistencia,
    })