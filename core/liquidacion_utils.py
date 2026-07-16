from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from django.apps import apps
from django.db.models import Sum

from .models import Liquidacion, Deuda

DECIMAL_2 = Decimal("0.01")


def d(valor):
    return Decimal(valor or 0).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)


def calcular_antiguedad_detalle(fecha_ingreso, fecha_salida):
    if not fecha_ingreso or not fecha_salida:
        return {"anios": 0, "meses": 0, "dias": 0, "meses_totales": 0}

    anios = fecha_salida.year - fecha_ingreso.year
    meses = fecha_salida.month - fecha_ingreso.month
    dias = fecha_salida.day - fecha_ingreso.day

    if dias < 0:
        meses -= 1
        mes_anterior = fecha_salida.month - 1 or 12
        anio_mes_anterior = fecha_salida.year if fecha_salida.month != 1 else fecha_salida.year - 1
        dias += monthrange(anio_mes_anterior, mes_anterior)[1]

    if meses < 0:
        anios -= 1
        meses += 12

    meses_totales = anios * 12 + meses
    return {
        "anios": max(anios, 0),
        "meses": max(meses, 0),
        "dias": max(dias, 0),
        "meses_totales": max(meses_totales, 0),
    }


def calcular_preaviso_dias(tipo_salida, fecha_ingreso, fecha_salida):
    if tipo_salida in [
        Liquidacion.TiposSalida.DESPIDO_JUSTA_CAUSA,
        Liquidacion.TiposSalida.PERIODO_PRUEBA,
        Liquidacion.TiposSalida.ABANDONO,
    ]:
        return 0

    detalle = calcular_antiguedad_detalle(fecha_ingreso, fecha_salida)
    meses_totales = detalle["meses_totales"]

    if meses_totales < 12:
        return 30
    if meses_totales < 60:
        return 45
    if meses_totales < 120:
        return 60
    return 90


def calcular_vacaciones_causadas_anuales(anios_antiguedad):
    if anios_antiguedad < 5:
        return 12
    if anios_antiguedad < 10:
        return 18
    return 30


def calcular_vacaciones_proporcionales_dias(fecha_ingreso, fecha_salida):
    if not fecha_ingreso or not fecha_salida:
        return 0

    antig = calcular_antiguedad_detalle(fecha_ingreso, fecha_salida)
    dias_anuales = calcular_vacaciones_causadas_anuales(antig["anios"])

    dia_del_anio = fecha_salida.timetuple().tm_yday
    dias_prop = int(
        (Decimal(dias_anuales) * Decimal(dia_del_anio) / Decimal(365)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return max(dias_prop, 0)


def calcular_aguinaldo_proporcional(salario_base, bono_base, fecha_salida):
    mensual = d(salario_base) + d(bono_base)
    meses_completos = max(fecha_salida.month - 1, 0)
    dias_mes = monthrange(fecha_salida.year, fecha_salida.month)[1]
    fraccion_mes = Decimal(fecha_salida.day) / Decimal(dias_mes)
    meses_equivalentes = Decimal(meses_completos) + fraccion_mes
    return (mensual * meses_equivalentes / Decimal(12)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)


def calcular_promedio_salarial_ultimos_6_meses(funcionario, fecha_salida):
    if not funcionario or not fecha_salida:
        return None

    try:
        NominaMensual = apps.get_model("core", "NominaMensual")
        nominas = (
            NominaMensual.objects.filter(
                funcionario=funcionario,
                anio__lte=fecha_salida.year,
            )
            .exclude(estado_pago=getattr(NominaMensual.EstadosPago, "ANULADO", "anulado"))
            .order_by("-anio", "-mes")
        )

        valores = []
        for nomina in nominas:
            if nomina.anio == fecha_salida.year and nomina.mes > fecha_salida.month:
                continue

            salario = d(getattr(nomina, "salario_bruto", 0) or getattr(nomina, "salario_base", 0))
            if salario > 0:
                valores.append(salario)

            if len(valores) == 6:
                break

        if not valores:
            return None

        return (sum(valores, d(0)) / Decimal(len(valores))).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def calcular_anios_computables_indemnizacion(fecha_ingreso, fecha_salida):
    detalle = calcular_antiguedad_detalle(fecha_ingreso, fecha_salida)
    suma_anio = detalle["meses"] > 6 or (detalle["meses"] == 6 and detalle["dias"] > 0)
    anios_computables = detalle["anios"] + (1 if suma_anio else 0)

    return {
        "anios_computables": max(anios_computables, 0),
        "suma_anio_por_fraccion": suma_anio,
        "antiguedad": detalle,
    }


def calcular_indemnizacion(tipo_salida, fecha_ingreso, fecha_salida, salario_base):
    if tipo_salida != Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA:
        return {
            "dias": 0,
            "monto": d(0),
            "revision": False,
            "alerta": "",
            "anios_computables": 0,
            "suma_anio_por_fraccion": False,
        }

    computo = calcular_anios_computables_indemnizacion(fecha_ingreso, fecha_salida)
    anios_computables = computo["anios_computables"]
    salario_diario = (d(salario_base) / Decimal(30)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)
    dias = anios_computables * 15
    monto = (salario_diario * Decimal(dias)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)

    return {
        "dias": dias,
        "monto": monto,
        "revision": False,
        "alerta": "",
        "anios_computables": anios_computables,
        "suma_anio_por_fraccion": computo["suma_anio_por_fraccion"],
    }


def calcular_deudas_activas_funcionario(funcionario):
    try:
        total = (
            Deuda.objects.filter(funcionario=funcionario, activa=True, aplicar_en_nomina=True)
            .aggregate(total=Sum("saldo_pendiente"))
            .get("total")
        )
        return d(total or 0)
    except Exception:
        return d(0)


def contar_ausencias_recientes_funcionario(funcionario, fecha_salida):
    if not funcionario or not fecha_salida:
        return 0

    try:
        Asistencia = apps.get_model("core", "Asistencia")
        fecha_inicio_mes = fecha_salida.replace(day=1)
        asistencias_qs = Asistencia.objects.filter(
            funcionario=funcionario,
            fecha__gte=fecha_inicio_mes,
            fecha__lte=fecha_salida,
        )
        fechas_asistidas = set(asistencias_qs.values_list("fecha", flat=True))

        ausencias = 0
        dia_actual = fecha_inicio_mes
        while dia_actual <= fecha_salida:
            if dia_actual.weekday() != 6 and dia_actual not in fechas_asistidas:
                ausencias += 1

            if dia_actual.day >= monthrange(dia_actual.year, dia_actual.month)[1]:
                break
            dia_actual = dia_actual.replace(day=dia_actual.day + 1)

        return ausencias
    except Exception:
        return 0


def construir_alertas_proteccion_liquidacion(resumen, tipo_salida):
    alertas = []
    tipo_display = dict(Liquidacion.TiposSalida.choices).get(tipo_salida, tipo_salida or "-")

    if resumen.get("ausencias_descuento", 0) > 0:
        alertas.append(
            f"Hay {resumen['ausencias_descuento']} ausencia(s) reciente(s) o pendiente(s) para revisar antes de confirmar."
        )

    dias_faltantes = resumen.get("preaviso_dias_faltantes", 0)
    if dias_faltantes > 0:
        alertas.append(
            f"Preaviso pendiente: corresponden {resumen.get('preaviso_dias_corresponde', 0)} dia(s), "
            f"se avisaron {resumen.get('preaviso_dias_otorgados', 0)} y faltan {dias_faltantes}."
        )

    if tipo_salida != Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA:
        alertas.append(f"El tipo de salida '{tipo_display}' no genera indemnizacion.")

    if resumen.get("indemnizacion_suma_anio_por_fraccion"):
        alertas.append("La fraccion de antiguedad supera 6 meses y suma 1 anio computable adicional.")

    if resumen.get("deudas_monto", d(0)) > 0:
        alertas.append("Hay deudas activas del funcionario para descontar o conciliar.")

    if resumen.get("otros_descuentos", d(0)) > 0:
        alertas.append("Hay otros descuentos cargados manualmente en esta liquidacion.")

    if resumen.get("vacaciones_causadas_pendientes_dias", 0) > 0:
        alertas.append("Hay vacaciones pendientes incluidas en la liquidacion.")

    return alertas


def calcular_liquidacion_funcionario(
    funcionario,
    tipo_salida,
    fecha_salida,
    dias_trabajados_pendientes=None,
    vacaciones_causadas_pendientes_dias=None,
    preaviso_dias_otorgados=0,
    preaviso_cumplido=False,
    descontar_preaviso=False,
    otros_descuentos=0,
):
    usa_salario_diferenciado = bool(getattr(funcionario, "usa_salario_diferenciado", False))
    modalidad_salarial = getattr(funcionario, "modalidad_salarial", "diferenciado" if usa_salario_diferenciado else "normal")
    salario_base_configurado = d(getattr(funcionario, "salario_base", 0))
    bono_configurado = d(getattr(funcionario, "bono", 0))
    salario_diferenciado = d(getattr(funcionario, "salario_diferenciado", 0)) if usa_salario_diferenciado else d(0)
    salario_base = d(getattr(funcionario, "salario_base_aplicable", salario_base_configurado))
    bono_base = d(getattr(funcionario, "bono_aplicable", bono_configurado))
    salario_mensual = d(getattr(funcionario, "salario_bruto_aplicable", salario_base + bono_base))
    salario_diario_base = (salario_mensual / Decimal(30)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)
    porcentaje_ips = Decimal("9.00")

    fecha_ingreso = getattr(funcionario, "fecha_ingreso", None)
    antig = calcular_antiguedad_detalle(fecha_ingreso, fecha_salida)
    preaviso_dias_corresponde = calcular_preaviso_dias(tipo_salida, fecha_ingreso, fecha_salida)

    dias_trabajados_pendientes = fecha_salida.day if fecha_salida else 0

    if vacaciones_causadas_pendientes_dias is None:
        vacaciones_causadas_pendientes_dias = 0

    vacaciones_causadas_pendientes_dias = int(vacaciones_causadas_pendientes_dias or 0)
    preaviso_dias_otorgados = int(preaviso_dias_otorgados or 0)

    salario_pendiente_monto = (salario_diario_base * Decimal(dias_trabajados_pendientes)).quantize(DECIMAL_2)
    vacaciones_causadas_monto = (salario_diario_base * Decimal(vacaciones_causadas_pendientes_dias)).quantize(DECIMAL_2)

    vacaciones_proporcionales_dias = calcular_vacaciones_proporcionales_dias(fecha_ingreso, fecha_salida)
    vacaciones_proporcionales_monto = (salario_diario_base * Decimal(vacaciones_proporcionales_dias)).quantize(DECIMAL_2)

    aguinaldo_proporcional_monto = calcular_aguinaldo_proporcional(salario_base, bono_base, fecha_salida)

    preaviso_monto = d(0)
    dias_faltantes_preaviso = max(preaviso_dias_corresponde - preaviso_dias_otorgados, 0)

    if tipo_salida == Liquidacion.TiposSalida.RENUNCIA:
        if descontar_preaviso and not preaviso_cumplido and dias_faltantes_preaviso > 0:
            preaviso_monto = (salario_diario_base * Decimal(dias_faltantes_preaviso)).quantize(DECIMAL_2)
    elif tipo_salida == Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA:
        if not preaviso_cumplido and dias_faltantes_preaviso > 0:
            preaviso_monto = (salario_diario_base * Decimal(dias_faltantes_preaviso)).quantize(DECIMAL_2)

    salario_indemnizacion = calcular_promedio_salarial_ultimos_6_meses(funcionario, fecha_salida) or salario_mensual
    indemnizacion = calcular_indemnizacion(tipo_salida, fecha_ingreso, fecha_salida, salario_indemnizacion)

    ips_monto = d(0)
    if getattr(funcionario, "ips", False):
        ips_monto = (salario_mensual * Decimal("0.09")).quantize(DECIMAL_2)

    deudas_monto = calcular_deudas_activas_funcionario(funcionario)
    otros_descuentos = d(otros_descuentos)
    ausencias_descuento = contar_ausencias_recientes_funcionario(funcionario, fecha_salida)
    descuento_ausencias = d(0)

    total_haberes = (
        salario_pendiente_monto
        + vacaciones_causadas_monto
        + vacaciones_proporcionales_monto
        + aguinaldo_proporcional_monto
        + indemnizacion["monto"]
    )

    total_descuentos = ips_monto + deudas_monto + otros_descuentos

    if tipo_salida == Liquidacion.TiposSalida.RENUNCIA and descontar_preaviso:
        total_descuentos += preaviso_monto
    elif tipo_salida == Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA:
        total_haberes += preaviso_monto

    total_liquidacion = (total_haberes - total_descuentos).quantize(DECIMAL_2)
    if total_liquidacion < 0:
        total_liquidacion = d(0)

    requiere_revision_juridica = indemnizacion["revision"]
    alerta_revision = indemnizacion["alerta"]

    if tipo_salida == Liquidacion.TiposSalida.ABANDONO:
        requiere_revision_juridica = True
        alerta_revision = "Caso cargado como abandono: verificar respaldo documental y causal antes de confirmar."

    resumen = {
        "modalidad_salarial_snapshot": modalidad_salarial,
        "salario_base_snapshot": salario_base_configurado,
        "bono_base_snapshot": bono_base,
        "salario_diferenciado_snapshot": salario_diferenciado,
        "salario_bruto_aplicable_snapshot": salario_mensual,
        "porcentaje_ips_snapshot": porcentaje_ips,
        "descuento_ips_calculado_snapshot": ips_monto,
        "salario_indemnizacion_base": salario_indemnizacion,
        "salario_diario_base": salario_diario_base,
        "antiguedad_anios": antig["anios"],
        "antiguedad_meses": antig["meses"],
        "antiguedad_dias": antig["dias"],
        "dias_trabajados_pendientes": dias_trabajados_pendientes,
        "salario_pendiente_monto": salario_pendiente_monto,
        "ausencias_descuento": ausencias_descuento,
        "descuento_ausencias": descuento_ausencias,
        "vacaciones_causadas_pendientes_dias": vacaciones_causadas_pendientes_dias,
        "vacaciones_causadas_monto": vacaciones_causadas_monto,
        "vacaciones_proporcionales_dias": vacaciones_proporcionales_dias,
        "vacaciones_proporcionales_monto": vacaciones_proporcionales_monto,
        "aguinaldo_proporcional_monto": aguinaldo_proporcional_monto,
        "preaviso_dias_corresponde": preaviso_dias_corresponde,
        "preaviso_dias_otorgados": preaviso_dias_otorgados,
        "preaviso_dias_faltantes": dias_faltantes_preaviso,
        "preaviso_cumplido": preaviso_cumplido,
        "descontar_preaviso": descontar_preaviso,
        "preaviso_monto": preaviso_monto,
        "indemnizacion_dias": indemnizacion["dias"],
        "indemnizacion_monto": indemnizacion["monto"],
        "indemnizacion_anios_computables": indemnizacion["anios_computables"],
        "indemnizacion_suma_anio_por_fraccion": indemnizacion["suma_anio_por_fraccion"],
        "ips_monto": ips_monto,
        "deudas_monto": deudas_monto,
        "otros_descuentos": otros_descuentos,
        "total_haberes": total_haberes,
        "total_descuentos": total_descuentos,
        "total_liquidacion": total_liquidacion,
        "total_haberes_automatico": total_haberes,
        "total_descuentos_automatico": total_descuentos,
        "total_liquidacion_automatico": total_liquidacion,
        "requiere_revision_juridica": requiere_revision_juridica,
        "alerta_revision": alerta_revision,
    }

    resumen["alertas_proteccion"] = construir_alertas_proteccion_liquidacion(resumen, tipo_salida)
    if not resumen["alerta_revision"] and resumen["alertas_proteccion"]:
        resumen["alerta_revision"] = resumen["alertas_proteccion"][0][:255]

    return resumen


def verificar_casos_liquidacion_manual():
    funcionario_4_8 = SimpleNamespace(
        salario_base=Decimal("3600000"),
        bono=Decimal("0"),
        fecha_ingreso=date(2021, 1, 15),
        ips=False,
    )
    fecha_salida = date(2025, 9, 15)

    funcionario_6_exactos = SimpleNamespace(
        salario_base=Decimal("3600000"),
        bono=Decimal("0"),
        fecha_ingreso=date(2025, 1, 15),
        ips=False,
    )

    funcionario_mas_6 = SimpleNamespace(
        salario_base=Decimal("3600000"),
        bono=Decimal("0"),
        fecha_ingreso=date(2025, 1, 15),
        ips=False,
    )

    return {
        "renuncia_4_anios_8_meses": calcular_liquidacion_funcionario(
            funcionario_4_8,
            Liquidacion.TiposSalida.RENUNCIA,
            fecha_salida,
        ),
        "despido_sin_justa_causa_4_anios_8_meses": calcular_liquidacion_funcionario(
            funcionario_4_8,
            Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA,
            fecha_salida,
        ),
        "despido_con_justa_causa": calcular_liquidacion_funcionario(
            funcionario_4_8,
            Liquidacion.TiposSalida.DESPIDO_JUSTA_CAUSA,
            fecha_salida,
        ),
        "fraccion_6_meses_exactos": calcular_liquidacion_funcionario(
            funcionario_6_exactos,
            Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA,
            date(2025, 7, 15),
        ),
        "fraccion_mayor_a_6_meses": calcular_liquidacion_funcionario(
            funcionario_mas_6,
            Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA,
            date(2025, 7, 16),
        ),
    }
