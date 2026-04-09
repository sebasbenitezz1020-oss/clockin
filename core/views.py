from calendar import monthrange
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    EmpresaForm,
    SucursalForm,
    FuncionarioForm,
    TurnoForm,
    MarcacionForm,
    PermisoLicenciaForm,
    VacacionForm,
)
from .models import (
    Empresa,
    Sucursal,
    Funcionario,
    Turno,
    Asistencia,
    PermisoLicencia,
    Vacacion,
    HistorialAccion,
)


def registrar_historial(request, modulo, accion, descripcion):
    HistorialAccion.objects.create(
        usuario=request.user if request.user.is_authenticated else None,
        modulo=modulo,
        accion=accion,
        descripcion=descripcion,
    )


@login_required
def dashboard(request):
    hoy = timezone.localdate()

    total_funcionarios = Funcionario.objects.filter(activo=True).count()

    asistencias_hoy_qs = Asistencia.objects.select_related(
        "funcionario",
        "funcionario__turno"
    ).filter(
        fecha=hoy,
        funcionario__activo=True
    )

    presentes_hoy = asistencias_hoy_qs.filter(
        hora_entrada__isnull=False
    ).count()

    llegadas_tarde_hoy = asistencias_hoy_qs.filter(
        llego_tarde=True
    ).count()

    salidas_hoy = asistencias_hoy_qs.filter(
        hora_salida__isnull=False
    ).count()

    pendientes_hoy = max(total_funcionarios - presentes_hoy, 0)

    trabajando_hoy = 0
    en_almuerzo_hoy = 0
    finalizados_hoy = 0

    for asistencia in asistencias_hoy_qs:
        estado = asistencia.estado_jornada
        if estado == "Trabajando":
            trabajando_hoy += 1
        elif estado == "En almuerzo":
            en_almuerzo_hoy += 1
        elif estado == "Finalizado":
            finalizados_hoy += 1

    ultimas_marcaciones = asistencias_hoy_qs.order_by("-actualizado_en")[:8]

    funcionarios_recientes = Funcionario.objects.filter(
        activo=True
    ).select_related(
        "turno",
        "sucursal_rel",
        "sucursal_rel__empresa"
    ).order_by("-creado_en")[:6]

    context = {
        "titulo": "Dashboard ClockIn",
        "hoy": hoy,
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
    }
    return render(request, "core/dashboard.html", context)


@login_required
def empresas_lista(request):
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
    if request.method == "POST":
        form = EmpresaForm(request.POST)
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
    empresa = get_object_or_404(Empresa, pk=pk)

    if request.method == "POST":
        form = EmpresaForm(request.POST, instance=empresa)
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
def funcionarios_lista(request):
    q = request.GET.get("q", "").strip()
    empresa_id = request.GET.get("empresa", "").strip()
    sucursal_id = request.GET.get("sucursal", "").strip()

    funcionarios = Funcionario.objects.select_related(
        "turno",
        "sucursal_rel",
        "sucursal_rel__empresa"
    ).all()

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

    if empresa_id:
        funcionarios = funcionarios.filter(sucursal_rel__empresa_id=empresa_id)

    if sucursal_id:
        funcionarios = funcionarios.filter(sucursal_rel_id=sucursal_id)

    empresas = Empresa.objects.filter(activo=True).order_by("nombre")
    sucursales = Sucursal.objects.filter(activo=True).order_by("nombre")

    if empresa_id:
        sucursales = sucursales.filter(empresa_id=empresa_id)

    context = {
        "funcionarios": funcionarios.order_by("apellido", "nombre"),
        "q": q,
        "empresas": empresas,
        "sucursales": sucursales,
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
    }
    return render(request, "core/funcionarios_lista.html", context)


@login_required
def funcionario_nuevo(request):
    if request.method == "POST":
        form = FuncionarioForm(request.POST, request.FILES)
        if form.is_valid():
            funcionario = form.save()
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

    return render(request, "core/funcionario_form.html", {
        "form": form,
        "titulo_form": "Nuevo funcionario",
        "boton_texto": "Guardar funcionario",
    })


@login_required
def funcionario_editar(request, pk):
    funcionario = get_object_or_404(Funcionario, pk=pk)

    if request.method == "POST":
        form = FuncionarioForm(request.POST, request.FILES, instance=funcionario)
        if form.is_valid():
            form.save()
            registrar_historial(
                request,
                "Funcionarios",
                "Editar",
                f"Se editó el funcionario {funcionario.nombre_completo} (CI: {funcionario.cedula})."
            )
            messages.success(request, "Funcionario actualizado correctamente.")
            return redirect("funcionarios_lista")
    else:
        form = FuncionarioForm(instance=funcionario)

    return render(request, "core/funcionario_form.html", {
        "form": form,
        "titulo_form": f"Editar funcionario: {funcionario.nombre_completo}",
        "boton_texto": "Guardar cambios",
        "funcionario": funcionario,
    })


@login_required
def funcionario_toggle_activo(request, pk):
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
    q = request.GET.get("q", "").strip()

    turnos = Turno.objects.all()

    if q:
        turnos = turnos.filter(nombre__icontains=q)

    context = {
        "turnos": turnos.order_by("nombre"),
        "q": q,
    }
    return render(request, "core/turnos_lista.html", context)


@login_required
def turno_nuevo(request):
    if request.method == "POST":
        form = TurnoForm(request.POST)
        if form.is_valid():
            turno = form.save()
            registrar_historial(
                request,
                "Turnos",
                "Crear",
                f"Se creó el turno {turno.nombre}."
            )
            messages.success(request, "Turno creado correctamente.")
            return redirect("turnos_lista")
    else:
        form = TurnoForm()

    return render(request, "core/turno_form.html", {
        "form": form,
        "titulo_form": "Nuevo turno",
        "boton_texto": "Guardar turno",
    })


@login_required
def turno_editar(request, pk):
    turno = get_object_or_404(Turno, pk=pk)

    if request.method == "POST":
        form = TurnoForm(request.POST, instance=turno)
        if form.is_valid():
            form.save()
            registrar_historial(
                request,
                "Turnos",
                "Editar",
                f"Se editó el turno {turno.nombre}."
            )
            messages.success(request, "Turno actualizado correctamente.")
            return redirect("turnos_lista")
    else:
        form = TurnoForm(instance=turno)

    return render(request, "core/turno_form.html", {
        "form": form,
        "titulo_form": f"Editar turno: {turno.nombre}",
        "boton_texto": "Guardar cambios",
        "turno": turno,
    })


@login_required
def turno_toggle_activo(request, pk):
    turno = get_object_or_404(Turno, pk=pk)
    turno.activo = not turno.activo
    turno.save()

    estado = "activado" if turno.activo else "inactivado"
    registrar_historial(
        request,
        "Turnos",
        "Cambio de estado",
        f"Turno {turno.nombre} fue {estado}."
    )
    messages.success(request, f"Turno {estado} correctamente.")
    return redirect("turnos_lista")


@login_required
def asistencia_marcar(request):
    hoy = timezone.localdate()
    resultado = None

    if request.method == "POST":
        form = MarcacionForm(request.POST)
        if form.is_valid():
            cedula = form.cleaned_data["cedula"].strip()

            try:
                funcionario = Funcionario.objects.select_related("turno").get(
                    cedula=cedula,
                    activo=True
                )
            except Funcionario.DoesNotExist:
                messages.error(request, "No se encontró un funcionario activo con esa cédula.")
                funcionario = None

            if funcionario:
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

    asistencias_hoy = Asistencia.objects.select_related("funcionario", "funcionario__turno").filter(
        fecha=hoy
    ).order_by("-hora_entrada")

    return render(request, "core/asistencia_marcar.html", {
        "form": form,
        "resultado": resultado,
        "asistencias_hoy": asistencias_hoy,
        "hoy": hoy,
    })


@login_required
def permisos_lista(request):
    q = request.GET.get("q", "").strip()

    permisos = PermisoLicencia.objects.select_related("funcionario").all()

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
    })


@login_required
def permiso_nuevo(request):
    if request.method == "POST":
        form = PermisoLicenciaForm(request.POST, request.FILES)
        if form.is_valid():
            permiso = form.save()
            registrar_historial(
                request,
                "Permisos/Licencias",
                "Crear",
                f"Se creó {permiso.get_tipo_display()} para {permiso.funcionario.nombre_completo} del {permiso.fecha_desde} al {permiso.fecha_hasta}."
            )
            messages.success(request, "Permiso/licencia creado correctamente.")
            return redirect("permisos_lista")
    else:
        form = PermisoLicenciaForm()

    return render(request, "core/permiso_form.html", {
        "form": form,
        "titulo_form": "Nuevo permiso / licencia",
        "boton_texto": "Guardar permiso",
    })


@login_required
def permiso_editar(request, pk):
    permiso = get_object_or_404(PermisoLicencia, pk=pk)

    if request.method == "POST":
        form = PermisoLicenciaForm(request.POST, request.FILES, instance=permiso)
        if form.is_valid():
            form.save()
            registrar_historial(
                request,
                "Permisos/Licencias",
                "Editar",
                f"Se editó {permiso.get_tipo_display()} de {permiso.funcionario.nombre_completo}. Estado actual: {permiso.get_estado_display()}."
            )
            messages.success(request, "Permiso/licencia actualizado correctamente.")
            return redirect("permisos_lista")
    else:
        form = PermisoLicenciaForm(instance=permiso)

    return render(request, "core/permiso_form.html", {
        "form": form,
        "titulo_form": "Editar permiso / licencia",
        "boton_texto": "Guardar cambios",
        "permiso": permiso,
    })


@login_required
def vacaciones_lista(request):
    q = request.GET.get("q", "").strip()

    vacaciones = Vacacion.objects.select_related("funcionario").all()

    if q:
        vacaciones = vacaciones.filter(
            Q(funcionario__nombre__icontains=q) |
            Q(funcionario__apellido__icontains=q) |
            Q(funcionario__cedula__icontains=q) |
            Q(estado__icontains=q)
        )

    funcionarios_resumen = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")

    return render(request, "core/vacaciones_lista.html", {
        "vacaciones": vacaciones,
        "funcionarios_resumen": funcionarios_resumen,
        "q": q,
    })


@login_required
def vacacion_nueva(request):
    if request.method == "POST":
        form = VacacionForm(request.POST)
        if form.is_valid():
            vacacion = form.save()
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

    return render(request, "core/vacacion_form.html", {
        "form": form,
        "titulo_form": "Nueva vacación",
        "boton_texto": "Guardar vacación",
    })


@login_required
def vacacion_editar(request, pk):
    vacacion = get_object_or_404(Vacacion, pk=pk)

    if request.method == "POST":
        form = VacacionForm(request.POST, instance=vacacion)
        if form.is_valid():
            form.save()
            registrar_historial(
                request,
                "Vacaciones",
                "Editar",
                f"Se editó vacación de {vacacion.funcionario.nombre_completo}. Estado actual: {vacacion.get_estado_display()}."
            )
            messages.success(request, "Vacación actualizada correctamente.")
            return redirect("vacaciones_lista")
    else:
        form = VacacionForm(instance=vacacion)

    return render(request, "core/vacacion_form.html", {
        "form": form,
        "titulo_form": "Editar vacación",
        "boton_texto": "Guardar cambios",
        "vacacion": vacacion,
    })


@login_required
def icl_lista(request):
    hoy = timezone.localdate()

    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    dias_mes = monthrange(anio, mes)[1]
    total_dias_laborales_estimados = sum(
        1 for dia in range(1, dias_mes + 1)
        if date(anio, mes, dia).weekday() != 6
    )

    funcionarios = Funcionario.objects.filter(
        activo=True
    ).select_related("turno").order_by("apellido", "nombre")

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

        ausencias_estimadas = max(total_dias_laborales_estimados - asistencias_count, 0)
        ausencias_justificadas = permisos_aprobados + vacaciones_aprobadas
        ausencias_no_justificadas = max(ausencias_estimadas - ausencias_justificadas, 0)

        icl = 100 - (atrasos_count * 2) - (ausencias_no_justificadas * 5)
        icl = max(0, min(100, icl))

        bono_base = float(funcionario.bono or 0)
        bono_proyectado = round(bono_base * (icl / 100), 2)

        resultados.append({
            "funcionario": funcionario,
            "asistencias": asistencias_count,
            "atrasos": atrasos_count,
            "ausencias_estimadas": ausencias_estimadas,
            "permisos_aprobados": permisos_aprobados,
            "vacaciones_aprobadas": vacaciones_aprobadas,
            "ausencias_no_justificadas": ausencias_no_justificadas,
            "icl": icl,
            "bono_base": bono_base,
            "bono_proyectado": bono_proyectado,
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
    })


@login_required
def reportes(request):
    hoy = timezone.localdate()

    fecha_str = request.GET.get("fecha", str(hoy))
    funcionario_id = request.GET.get("funcionario", "")
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    try:
        fecha_reporte = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        fecha_reporte = hoy

    funcionarios = Funcionario.objects.filter(activo=True).order_by("apellido", "nombre")

    asistencias_dia = Asistencia.objects.select_related("funcionario", "funcionario__turno").filter(
        fecha=fecha_reporte
    )

    if funcionario_id:
        asistencias_dia = asistencias_dia.filter(funcionario_id=funcionario_id)

    presentes_dia = asistencias_dia.filter(hora_entrada__isnull=False).count()
    tardanzas_dia = asistencias_dia.filter(llego_tarde=True).count()
    salidas_dia = asistencias_dia.filter(hora_salida__isnull=False).count()

    resultados_mensuales = []
    funcionarios_para_mes = funcionarios

    if funcionario_id:
        funcionarios_para_mes = funcionarios_para_mes.filter(id=funcionario_id)

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
        ausencias_estimadas = max(total_dias_laborales_estimados - asistencias_count, 0)

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

        icl = 100 - (atrasos_count * 2) - (ausencias_estimadas * 5)
        icl = max(0, min(100, icl))

        resultados_mensuales.append({
            "funcionario": funcionario,
            "asistencias": asistencias_count,
            "atrasos": atrasos_count,
            "ausencias": ausencias_estimadas,
            "permisos_aprobados": permisos_aprobados,
            "vacaciones_aprobadas": vacaciones_aprobadas,
            "icl": icl,
        })

    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]
    anios = list(range(hoy.year - 2, hoy.year + 2))

    return render(request, "core/reportes.html", {
        "fecha_reporte": fecha_reporte,
        "funcionarios": funcionarios,
        "funcionario_id": funcionario_id,
        "asistencias_dia": asistencias_dia.order_by("funcionario__apellido", "funcionario__nombre"),
        "presentes_dia": presentes_dia,
        "tardanzas_dia": tardanzas_dia,
        "salidas_dia": salidas_dia,
        "mes": mes,
        "anio": anio,
        "meses": meses,
        "anios": anios,
        "resultados_mensuales": resultados_mensuales,
    })


@login_required
def historial_lista(request):
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