from calendar import monthrange
from decimal import Decimal, ROUND_HALF_UP

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
        Liquidacion.TiposSalida.ABANDONO,
    ]:
        return 0

    detalle = calcular_antiguedad_detalle(fecha_ingreso, fecha_salida)
    meses_totales = detalle["meses_totales"]

    if meses_totales < 12:
        return 30
    elif meses_totales < 60:
        return 45
    elif meses_totales < 120:
        return 60
    return 90


def calcular_vacaciones_causadas_anuales(anios_antiguedad):
    if anios_antiguedad < 5:
        return 12
    elif anios_antiguedad < 10:
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


def calcular_indemnizacion(tipo_salida, fecha_ingreso, fecha_salida, salario_base):
    if tipo_salida != Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA:
        return {"dias": 0, "monto": d(0), "revision": False, "alerta": ""}

    detalle = calcular_antiguedad_detalle(fecha_ingreso, fecha_salida)
    anios = detalle["anios"]
    meses = detalle["meses"]

    salario_diario = (d(salario_base) / Decimal(30)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)

    if anios >= 10:
        dias = 30
        monto = (salario_diario * Decimal(dias)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)
        return {
            "dias": dias,
            "monto": monto,
            "revision": True,
            "alerta": "Funcionario con 10 años o más de antigüedad: revisar estabilidad especial antes de confirmar.",
        }

    dias = anios * 15
    if meses >= 6:
        dias += 15

    monto = (salario_diario * Decimal(dias)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)
    return {"dias": dias, "monto": monto, "revision": False, "alerta": ""}


def calcular_deudas_activas_funcionario(funcionario):
    total = (
        Deuda.objects.filter(funcionario=funcionario, activa=True, aplicar_en_nomina=True)
        .aggregate(total=Sum("saldo_pendiente"))
        .get("total")
    )
    return d(total or 0)


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
    salario_base = d(funcionario.salario_base)
    bono_base = d(funcionario.bono)
    salario_mensual = salario_base + bono_base
    salario_diario = (salario_mensual / Decimal(30)).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)

    antig = calcular_antiguedad_detalle(funcionario.fecha_ingreso, fecha_salida)
    preaviso_dias_corresponde = calcular_preaviso_dias(tipo_salida, funcionario.fecha_ingreso, fecha_salida)

    if dias_trabajados_pendientes is None:
        dias_trabajados_pendientes = fecha_salida.day

    if vacaciones_causadas_pendientes_dias is None:
        vacaciones_causadas_pendientes_dias = 0

    dias_trabajados_pendientes = int(dias_trabajados_pendientes or 0)
    vacaciones_causadas_pendientes_dias = int(vacaciones_causadas_pendientes_dias or 0)
    preaviso_dias_otorgados = int(preaviso_dias_otorgados or 0)

    salario_pendiente_monto = (salario_diario * Decimal(dias_trabajados_pendientes)).quantize(DECIMAL_2)
    vacaciones_causadas_monto = (salario_diario * Decimal(vacaciones_causadas_pendientes_dias)).quantize(DECIMAL_2)

    vacaciones_proporcionales_dias = calcular_vacaciones_proporcionales_dias(funcionario.fecha_ingreso, fecha_salida)
    vacaciones_proporcionales_monto = (salario_diario * Decimal(vacaciones_proporcionales_dias)).quantize(DECIMAL_2)

    aguinaldo_proporcional_monto = calcular_aguinaldo_proporcional(salario_base, bono_base, fecha_salida)

    preaviso_monto = d(0)
    dias_faltantes_preaviso = max(preaviso_dias_corresponde - preaviso_dias_otorgados, 0)

    if tipo_salida == Liquidacion.TiposSalida.RENUNCIA:
        if descontar_preaviso and not preaviso_cumplido and dias_faltantes_preaviso > 0:
            preaviso_monto = (salario_diario * Decimal(dias_faltantes_preaviso)).quantize(DECIMAL_2)

    elif tipo_salida == Liquidacion.TiposSalida.DESPIDO_SIN_JUSTA_CAUSA:
        if not preaviso_cumplido and dias_faltantes_preaviso > 0:
            preaviso_monto = (salario_diario * Decimal(dias_faltantes_preaviso)).quantize(DECIMAL_2)

    indemnizacion = calcular_indemnizacion(tipo_salida, funcionario.fecha_ingreso, fecha_salida, salario_base)

    ips_monto = d(0)
    if funcionario.ips:
        ips_monto = (salario_pendiente_monto * Decimal("0.09")).quantize(DECIMAL_2)

    deudas_monto = calcular_deudas_activas_funcionario(funcionario)
    otros_descuentos = d(otros_descuentos)

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

    return {
        "salario_base_snapshot": salario_base,
        "bono_base_snapshot": bono_base,
        "antiguedad_anios": antig["anios"],
        "antiguedad_meses": antig["meses"],
        "antiguedad_dias": antig["dias"],
        "dias_trabajados_pendientes": dias_trabajados_pendientes,
        "salario_pendiente_monto": salario_pendiente_monto,
        "vacaciones_causadas_pendientes_dias": vacaciones_causadas_pendientes_dias,
        "vacaciones_causadas_monto": vacaciones_causadas_monto,
        "vacaciones_proporcionales_dias": vacaciones_proporcionales_dias,
        "vacaciones_proporcionales_monto": vacaciones_proporcionales_monto,
        "aguinaldo_proporcional_monto": aguinaldo_proporcional_monto,
        "preaviso_dias_corresponde": preaviso_dias_corresponde,
        "preaviso_dias_otorgados": preaviso_dias_otorgados,
        "preaviso_cumplido": preaviso_cumplido,
        "descontar_preaviso": descontar_preaviso,
        "preaviso_monto": preaviso_monto,
        "indemnizacion_dias": indemnizacion["dias"],
        "indemnizacion_monto": indemnizacion["monto"],
        "ips_monto": ips_monto,
        "deudas_monto": deudas_monto,
        "otros_descuentos": otros_descuentos,
        "total_haberes": total_haberes,
        "total_descuentos": total_descuentos,
        "total_liquidacion": total_liquidacion,
        "requiere_revision_juridica": requiere_revision_juridica,
        "alerta_revision": alerta_revision,
    }