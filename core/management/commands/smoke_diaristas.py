from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from core.forms import AsistenciaDiaristaForm, DiaristaForm, PagoDiaristaForm
from core.models import AsistenciaDiarista, Diarista, Empresa, PagoDiarista
from core.views import (
    _actualizar_calculos_asistencia_diarista,
    _datetime_jornada,
    diarista_cambiar_estado,
    diarista_pago_pdf,
    diaristas_reporte,
)


class SmokeRollback(Exception):
    pass


class Command(BaseCommand):
    help = "Ejecuta una prueba integral no persistente del modulo Diaristas."

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                self._run_smoke()
                raise SmokeRollback()
        except SmokeRollback:
            self.stdout.write(self.style.SUCCESS("Smoke Diaristas OK. Transaccion revertida; no se dejaron datos de prueba."))

    def _request(self, method, path, user, data=None):
        factory = RequestFactory(HTTP_HOST="127.0.0.1:8000")
        request = getattr(factory, method.lower())(path, data=data or {})
        request.user = user
        request.session = {}
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def _run_smoke(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="smoke_diaristas_user",
            password="test",
            is_superuser=True,
            is_staff=True,
        )
        empresa = Empresa.objects.create(nombre="Smoke Diaristas S.R.L.", ruc="80000000-0", activo=True)

        form = DiaristaForm(data={
            "empresa": str(empresa.pk),
            "nombres": "Ana",
            "apellidos": "Duarte",
            "cedula": "999001",
            "telefono": "",
            "direccion": "",
            "fecha_nacimiento": "",
            "fecha_inicio": date.today().isoformat(),
            "fecha_fin": date.today().isoformat(),
            "cantidad_dias_contratados": "1",
            "monto_diario_acordado": "120000",
            "forma_calculo": Diarista.FormasCalculo.POR_DIA_TRABAJADO,
            "turno": "",
            "sector": "",
            "funcion_temporal": "Prueba operativa",
            "observaciones": "",
            "estado": Diarista.Estados.ACTIVO,
            "activo": "on",
        })
        if not form.is_valid():
            raise AssertionError(f"DiaristaForm invalido: {form.errors}")
        diarista = form.save(commit=False)
        diarista.creado_por = user
        diarista.save()

        asistencia_form = AsistenciaDiaristaForm(data={
            "fecha": date.today().isoformat(),
            "hora_entrada_simple": "08:00",
            "hora_salida_simple": "16:00",
            "estado": AsistenciaDiarista.Estados.TRABAJADO,
            "observacion": "Smoke test",
        })
        if not asistencia_form.is_valid():
            raise AssertionError(f"AsistenciaDiaristaForm invalido: {asistencia_form.errors}")
        asistencia = asistencia_form.save(commit=False)
        asistencia.diarista = diarista
        asistencia.empresa = empresa
        asistencia.origen_marcacion = "manual"
        asistencia.hora_entrada = _datetime_jornada(asistencia.fecha, asistencia_form.cleaned_data["hora_entrada_simple"])
        asistencia.hora_salida = _datetime_jornada(asistencia.fecha, asistencia_form.cleaned_data["hora_salida_simple"])
        _actualizar_calculos_asistencia_diarista(asistencia)
        asistencia.save()
        if asistencia.minutos_trabajados != 480:
            raise AssertionError("La asistencia de diarista no calculo 480 minutos trabajados.")

        pago_form = PagoDiaristaForm(data={
            "fecha_pago": date.today().isoformat(),
            "periodo_desde": date.today().isoformat(),
            "periodo_hasta": date.today().isoformat(),
            "monto_diario_aplicado": "120000",
            "adicionales": "0",
            "descuentos": "0",
            "concepto_adicional": "",
            "motivo_ajuste": "",
            "observacion": "Smoke test",
            "marcar_pagado": "on",
        }, diarista=diarista)
        if not pago_form.is_valid():
            raise AssertionError(f"PagoDiaristaForm invalido: {pago_form.errors}")
        pago = pago_form.save(commit=False)
        pago.diarista = diarista
        pago.empresa = empresa
        pago.dias_calculados = Decimal("1")
        pago.generado_por = user
        pago.estado = PagoDiarista.Estados.PAGADO
        pago.calcular_total()
        pago.save()
        pago.numero_comprobante = f"DIA-{pago.fecha_pago:%Y%m%d}-{pago.pk:05d}"
        pago.save(update_fields=["numero_comprobante"])
        asistencia.pago = pago
        asistencia.pago_estado = AsistenciaDiarista.EstadosPago.PAGADO
        asistencia.save(update_fields=["pago", "pago_estado"])
        if pago.total_pagado != Decimal("120000"):
            raise AssertionError("El pago de diarista no calculo el total esperado.")

        for name, args in [
            ("diaristas_lista", []),
            ("diaristas_reporte", []),
            ("diarista_detalle", [diarista.pk]),
            ("diarista_asistencias", [diarista.pk]),
            ("diarista_pagos", [diarista.pk]),
            ("diarista_pago_detalle", [diarista.pk, pago.pk]),
            ("diarista_pago_pdf", [diarista.pk, pago.pk]),
            ("diarista_cambiar_estado", [diarista.pk]),
        ]:
            reverse(name, args=args)

        request = self._request("get", reverse("diarista_pago_pdf", args=[diarista.pk, pago.pk]), user)
        response = diarista_pago_pdf(request, diarista.pk, pago.pk)
        if response.status_code != 200 or response["Content-Type"] != "application/pdf" or len(response.content) < 1000:
            raise AssertionError("El PDF de pago de diarista no se genero correctamente.")

        request = self._request("get", reverse("diaristas_reporte") + "?export=csv", user)
        response = diaristas_reporte(request)
        if response.status_code != 200 or "text/csv" not in response["Content-Type"]:
            raise AssertionError("El CSV de reporte de diaristas no se genero correctamente.")

        request = self._request("post", reverse("diarista_cambiar_estado", args=[diarista.pk]), user, {"accion": "finalizar"})
        response = diarista_cambiar_estado(request, diarista.pk)
        diarista.refresh_from_db()
        asistencia.refresh_from_db()
        pago.refresh_from_db()
        if response.status_code != 302 or diarista.estado != Diarista.Estados.FINALIZADO or diarista.activo:
            raise AssertionError("El cambio de estado de diarista no funciono correctamente.")
        if pago.estado != PagoDiarista.Estados.PAGADO or asistencia.pago_estado != AsistenciaDiarista.EstadosPago.PAGADO:
            raise AssertionError("El cambio de estado altero pagos o jornadas, y no debe hacerlo.")
