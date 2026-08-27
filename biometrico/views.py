import base64
import hashlib
import json
import logging
from io import BytesIO

import cv2
import face_recognition
import numpy as np
from PIL import Image

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import Asistencia, Empresa, Funcionario, Sucursal
from core.views import registrar_historial
from usuarios.multiempresa import es_admin_master, obtener_empresa_activa, obtener_empresa_usuario
from usuarios.utils import tiene_permiso


# =====================================================
# CONFIGURACIÓN PRO DE RENDIMIENTO
# =====================================================
FACE_TOLERANCE = 0.60
FACE_TOLERANCE_SEGURA = 0.52
FACE_TOLERANCE_DUDOSA = 0.60

BRILLO_MINIMO = 55
BRILLO_OPTIMO = 75

BLOQUEO_MISMO_ROSTRO_SEGUNDOS = 5
MIN_SEGUNDOS_ENTRE_PROCESOS = 0.65

CACHE_ROSTROS = {
    "data": None,
    "count": 0,
}

ULTIMO_RECONOCIDO = {
    "funcionario_id": None,
    "tiempo": None,
}

ULTIMO_PROCESO = None

logger = logging.getLogger(__name__)


# =====================================================
# HELPERS
# =====================================================
def _base64_a_frame(data_url):
    try:
        _, encoded = data_url.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None


def _base64_a_rgb_np(data_url):
    try:
        image_data = base64.b64decode(data_url.split(",")[1])
        image = Image.open(BytesIO(image_data)).convert("RGB")
        return np.array(image)
    except Exception:
        return None


def _mensaje_error_amigable(error_texto):
    texto = str(error_texto or "").lower()

    if "sizes of input arguments do not match" in texto:
        return "No fue posible validar el rostro. Ajuste el rostro dentro del recuadro e intente nuevamente."

    if "could not open" in texto or "cannot open" in texto:
        return "No se pudo procesar la imagen capturada. Intente nuevamente."

    if "no face" in texto or "rostro" in texto:
        return "No se detectó un rostro válido. Colóquese de frente a la cámara."

    return "No fue posible validar el rostro. Intente nuevamente."


def _controlar_frecuencia_backend():
    global ULTIMO_PROCESO

    ahora = timezone.now()

    if ULTIMO_PROCESO is None:
        ULTIMO_PROCESO = ahora
        return True

    diferencia = (ahora - ULTIMO_PROCESO).total_seconds()

    if diferencia < MIN_SEGUNDOS_ENTRE_PROCESOS:
        return False

    ULTIMO_PROCESO = ahora
    return True


def _bloqueo_por_rostro(funcionario_id):
    ahora = timezone.now()

    if ULTIMO_RECONOCIDO["funcionario_id"] == funcionario_id and ULTIMO_RECONOCIDO["tiempo"]:
        diferencia = (ahora - ULTIMO_RECONOCIDO["tiempo"]).total_seconds()

        if diferencia < BLOQUEO_MISMO_ROSTRO_SEGUNDOS:
            return False

    ULTIMO_RECONOCIDO["funcionario_id"] = funcionario_id
    ULTIMO_RECONOCIDO["tiempo"] = ahora
    return True


def _cargar_rostros_cache():
    funcionarios = Funcionario.objects.filter(
        activo=True,
        face_encoding__isnull=False
    ).only("id", "nombre", "apellido", "cedula", "face_encoding")

    total_actual = funcionarios.count()

    if CACHE_ROSTROS["data"] is not None and CACHE_ROSTROS["count"] == total_actual:
        return CACHE_ROSTROS["data"]

    data = []

    for funcionario in funcionarios:
        try:
            encoding = np.frombuffer(funcionario.face_encoding, dtype=np.float64)

            if encoding.shape[0] == 128:
                data.append({
                    "funcionario": funcionario,
                    "encoding": encoding,
                })
        except Exception:
            continue

    CACHE_ROSTROS["data"] = data
    CACHE_ROSTROS["count"] = total_actual

    return data


def _limpiar_cache_rostros():
    CACHE_ROSTROS["data"] = None
    CACHE_ROSTROS["count"] = 0


def _permitir_laboratorio_offline(request):
    return (
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or settings.DEBUG
        )
    )


def _token_laboratorio_funcionario(funcionario_id):
    texto = f"fase0:{settings.SECRET_KEY}:{funcionario_id}".encode("utf-8")
    return hashlib.sha256(texto).hexdigest()[:16]


def _tiene_permiso_biometrico(request, accion="puede_ver"):
    return tiene_permiso(request.user, "biometrico", accion)


def _empresas_biometricas_permitidas(request):
    if es_admin_master(request.user):
        return Empresa.objects.filter(activo=True).order_by("nombre")

    empresa = obtener_empresa_usuario(request.user)
    if not empresa:
        return Empresa.objects.none()
    return Empresa.objects.filter(pk=empresa.pk, activo=True)


def _empresa_biometrica_seleccionada(request):
    empresas = _empresas_biometricas_permitidas(request)
    empresa_id = request.GET.get("empresa") or request.POST.get("empresa")

    if empresa_id:
        empresa = empresas.filter(pk=empresa_id).first()
        if empresa:
            return empresa, empresas
        return None, empresas

    empresa_activa = obtener_empresa_activa(request)
    if empresa_activa and empresas.filter(pk=empresa_activa.pk).exists():
        return empresa_activa, empresas

    if empresas.count() == 1:
        return empresas.first(), empresas

    return empresas.first(), empresas


def _funcionarios_biometricos_base(empresa):
    if not empresa:
        return Funcionario.objects.none()
    return Funcionario.objects.filter(
        activo=True,
        sucursal_rel__empresa=empresa,
    ).select_related("sucursal_rel", "turno")


def _descriptor_facial_valido(funcionario):
    encoding = funcionario.face_encoding
    if not encoding:
        return False
    try:
        return np.frombuffer(encoding, dtype=np.float64).shape[0] == 128
    except Exception:
        return False


def _validar_borrosidad(image_np):
    try:
        gris = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        varianza = cv2.Laplacian(gris, cv2.CV_64F).var()
        if varianza < 35:
            return False, "imagen_borrosa", "La imagen está borrosa. Intente con una foto más nítida."
    except Exception:
        pass
    return True, "nitidez_ok", "Imagen nítida."


def _procesar_registro_rostro(funcionario, data, origen="CAMARA", guardar=True):
    if not data:
        return {"ok": False, "tipo": "sin_imagen", "error": "No se recibió imagen."}

    if len(data) > 8_500_000:
        return {"ok": False, "tipo": "archivo_grande", "error": "La imagen es demasiado pesada. Seleccione una foto más liviana."}

    image_np = _base64_a_rgb_np(data)
    if image_np is None:
        return {"ok": False, "tipo": "error_imagen", "error": "No se pudo procesar la imagen. Use JPG, PNG o WEBP."}

    alto, ancho = image_np.shape[:2]
    if ancho < 360 or alto < 360:
        return {"ok": False, "tipo": "resolucion_baja", "error": "La imagen tiene poca resolución. Use una foto más clara y cercana."}

    ok_luz, tipo_luz, mensaje_luz = _validar_iluminacion(image_np)
    if not ok_luz:
        return {"ok": False, "tipo": tipo_luz, "error": mensaje_luz or "Mejore la iluminación."}

    ok_blur, tipo_blur, mensaje_blur = _validar_borrosidad(image_np)
    if not ok_blur:
        return {"ok": False, "tipo": tipo_blur, "error": mensaje_blur}

    small = cv2.resize(image_np, (0, 0), fx=0.65, fy=0.65)
    face_locations_small = face_recognition.face_locations(small, model="hog")

    if not face_locations_small:
        return {"ok": False, "tipo": "sin_rostro", "error": "No se detectó un rostro. Colóquese de frente a la cámara."}

    if len(face_locations_small) > 1:
        return {"ok": False, "tipo": "multiples_rostros", "error": "Se detectó más de una persona. Debe aparecer una sola persona."}

    scale = 1 / 0.65
    top, right, bottom, left = face_locations_small[0]
    face_location = (int(top * scale), int(right * scale), int(bottom * scale), int(left * scale))
    ok_posicion, tipo_posicion, mensaje_posicion = _validar_rostro_centrado(image_np, face_location)
    if not ok_posicion:
        return {"ok": False, "tipo": tipo_posicion, "error": mensaje_posicion or "Ajuste el rostro dentro del marco."}

    encodings = face_recognition.face_encodings(small, face_locations_small)
    if not encodings:
        return {"ok": False, "tipo": "sin_descriptor", "error": "No se pudo generar el registro facial. Intente nuevamente."}

    era_actualizacion = bool(funcionario.face_encoding)
    if guardar:
        funcionario.face_encoding = encodings[0].tobytes()
        funcionario.save(update_fields=["face_encoding", "actualizado_en"])
        _limpiar_cache_rostros()

    return {
        "ok": True,
        "tipo": "actualizacion" if era_actualizacion else "registro",
        "mensaje": f"Rostro guardado para {funcionario.nombre_completo}" if guardar else "Rostro detectado correctamente.",
        "origen": origen if origen in ["CAMARA", "ARCHIVO"] else "CAMARA",
        "era_actualizacion": era_actualizacion,
        "guardado": guardar,
    }


def _validar_iluminacion(image_np):
    try:
        gris = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        brillo = float(np.mean(gris))

        if brillo < BRILLO_MINIMO:
            return False, "luz_baja", "Mejore la iluminación del rostro."

        if brillo < BRILLO_OPTIMO:
            return True, "luz_media", "Iluminación aceptable."

        return True, "luz_ok", "Iluminación correcta."
    except Exception:
        return True, "luz_ok", None


def _validar_rostro_centrado(image_np, face_location):
    try:
        top, right, bottom, left = face_location

        alto, ancho = image_np.shape[:2]

        centro_x = (left + right) / 2
        centro_y = (top + bottom) / 2

        margen_x_min = ancho * 0.22
        margen_x_max = ancho * 0.78
        margen_y_min = alto * 0.15
        margen_y_max = alto * 0.85

        ancho_rostro = right - left
        alto_rostro = bottom - top

        porcentaje_ancho = ancho_rostro / ancho
        porcentaje_alto = alto_rostro / alto

        if centro_x < margen_x_min:
            return False, "posicion_izquierda", "Mueva el rostro un poco hacia la derecha."

        if centro_x > margen_x_max:
            return False, "posicion_derecha", "Mueva el rostro un poco hacia la izquierda."

        if centro_y < margen_y_min:
            return False, "posicion_arriba", "Baje un poco el rostro dentro del recuadro."

        if centro_y > margen_y_max:
            return False, "posicion_abajo", "Suba un poco el rostro dentro del recuadro."

        if porcentaje_ancho < 0.16 or porcentaje_alto < 0.16:
            return False, "muy_lejos", "Acérquese un poco más a la cámara."

        if porcentaje_ancho > 0.62 or porcentaje_alto > 0.75:
            return False, "muy_cerca", "Aléjese un poco de la cámara."

        return True, "rostro_ok", "Rostro centrado correctamente."

    except Exception:
        return True, "rostro_ok", None


def _detectar_rostros_simple(frame_bgr):
    try:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        small = cv2.resize(rgb, (0, 0), fx=0.35, fy=0.35)
        face_locations = face_recognition.face_locations(small, model="hog")
        return face_locations
    except Exception:
        return []


def _analizar_frame_basico(frame_bgr):
    try:
        if frame_bgr is None:
            return {
                "hay_rostro": False,
                "cantidad_rostros": 0,
                "tipo": "error_imagen",
                "mensaje": "No se pudo procesar la imagen.",
            }

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        brillo = float(np.mean(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)))

        small = cv2.resize(rgb, (0, 0), fx=0.35, fy=0.35)
        face_locations_small = face_recognition.face_locations(small, model="hog")

        if brillo < BRILLO_MINIMO:
            return {
                "hay_rostro": len(face_locations_small) > 0,
                "cantidad_rostros": len(face_locations_small),
                "tipo": "luz_baja",
                "mensaje": "Mejore la iluminación del rostro.",
            }

        if not face_locations_small:
            return {
                "hay_rostro": False,
                "cantidad_rostros": 0,
                "tipo": "sin_rostro",
                "mensaje": "Esperando rostro frente a cámara.",
            }

        if len(face_locations_small) > 1:
            return {
                "hay_rostro": True,
                "cantidad_rostros": len(face_locations_small),
                "tipo": "multiples_rostros",
                "mensaje": "Debe acercarse una sola persona a la cámara.",
            }

        scale = 1 / 0.35
        top, right, bottom, left = face_locations_small[0]
        face_location = (
            int(top * scale),
            int(right * scale),
            int(bottom * scale),
            int(left * scale),
        )

        ok_posicion, tipo_posicion, mensaje_posicion = _validar_rostro_centrado(rgb, face_location)

        if not ok_posicion:
            return {
                "hay_rostro": True,
                "cantidad_rostros": 1,
                "tipo": tipo_posicion,
                "mensaje": mensaje_posicion,
            }

        return {
            "hay_rostro": True,
            "cantidad_rostros": 1,
            "tipo": "rostro_listo",
            "mensaje": "Rostro listo para validar.",
        }

    except Exception:
        return {
            "hay_rostro": False,
            "cantidad_rostros": 0,
            "tipo": "error_validacion",
            "mensaje": "No fue posible analizar el rostro.",
        }


def _reconocer_desde_imagen(image_np):
    rostros_guardados = _cargar_rostros_cache()

    if not rostros_guardados:
        return None, "No hay rostros registrados en el sistema.", "sin_registros"

    try:
        ok_luz, tipo_luz, mensaje_luz = _validar_iluminacion(image_np)
        if not ok_luz:
            return None, mensaje_luz, tipo_luz

        if image_np.shape[1] > 720:
            scale = 720 / image_np.shape[1]
            image_np = cv2.resize(
                image_np,
                (720, int(image_np.shape[0] * scale)),
                interpolation=cv2.INTER_AREA,
            )

        face_locations = face_recognition.face_locations(image_np, model="hog")

        if not face_locations:
            return None, "No se detectó un rostro válido.", "sin_rostro"

        if len(face_locations) > 1:
            return None, "Se detectaron varios rostros. Debe acercarse una sola persona.", "multiples_rostros"

        ok_centro, tipo_centro, mensaje_centro = _validar_rostro_centrado(image_np, face_locations[0])
        if not ok_centro:
            return None, mensaje_centro, tipo_centro

        face_encodings = face_recognition.face_encodings(image_np, face_locations)

        if not face_encodings:
            return None, "No se pudo codificar el rostro. Mire de frente a la cámara.", "no_codificado"

        encoding_actual = face_encodings[0]

        known_encodings = [item["encoding"] for item in rostros_guardados]
        distances = face_recognition.face_distance(known_encodings, encoding_actual)

        if len(distances) == 0:
            return None, "No hay rostros válidos para comparar.", "sin_comparacion"

        mejor_indice = int(np.argmin(distances))
        mejor_distancia = float(distances[mejor_indice])

        if mejor_distancia <= FACE_TOLERANCE_SEGURA:
            return rostros_guardados[mejor_indice]["funcionario"], None, "coincidencia_segura"

        if mejor_distancia <= FACE_TOLERANCE_DUDOSA:
            return rostros_guardados[mejor_indice]["funcionario"], None, "coincidencia_aceptable"

        if mejor_distancia <= 0.68:
            return None, "Rostro parecido, pero no suficientemente claro. Acérquese y mire de frente.", "coincidencia_dudosa"

        return None, "Rostro detectado, pero no fue reconocido.", "no_reconocido"

    except Exception:
        return None, "No fue posible comparar el rostro.", "error_validacion"


# =====================================================
# ASISTENCIA BIOMÉTRICA
# =====================================================

def obtener_fecha_operativa_asistencia(funcionario, ahora=None):
    ahora = ahora or timezone.localtime()
    hoy = ahora.date()

    if not funcionario.turno:
        return hoy

    turno = funcionario.turno

    # Turno normal: no cruza medianoche
    if turno.hora_salida > turno.hora_entrada:
        return hoy

    # Turno nocturno: ejemplo 17:00 a 01:00
    ayer = hoy - timezone.timedelta(days=1)

    asistencia_ayer = Asistencia.objects.filter(
        funcionario=funcionario,
        fecha=ayer,
        hora_entrada__isnull=False,
        hora_salida__isnull=True,
    ).first()

    if asistencia_ayer:
        return ayer

    return hoy


def _codigo_resultado_biometrico(resultado, modo):
    tipo = resultado.get("tipo")

    if resultado.get("ok"):
        if tipo in ["entrada", "regreso_almuerzo"]:
            return "SUCCESS_ENTRY"
        if tipo in ["salida", "salida_almuerzo"]:
            return "SUCCESS_EXIT"
        return "SUCCESS"

    if tipo in ["espera_salida_almuerzo", "espera_salida_final"]:
        return "ALREADY_ENTRY"
    if tipo == "espera_regreso_almuerzo":
        return "ALREADY_EXIT"
    if tipo == "ya_completo":
        return "ALREADY_EXIT" if modo == "salida" else "ALREADY_COMPLETE"
    if tipo == "sin_entrada":
        return "PENDING_ENTRY"
    if tipo in ["modo_invalido", "error"]:
        return "TECHNICAL_ERROR"
    return "TECHNICAL_ERROR"

def _marcar_asistencia_biometrica(request, funcionario, modo, origen="biometrico_tablet"):
    ahora = timezone.localtime()
    fecha_operativa = obtener_fecha_operativa_asistencia(funcionario, ahora)
    origen = origen if origen in ["biometrico_tablet", "biometrico_celular"] else "biometrico_tablet"

    if modo not in ["entrada", "salida"]:
        return {
            "ok": False,
            "tipo": "modo_invalido",
            "mensaje": "Modo de marcación inválido."
        }

    if not funcionario.activo:
        return {
            "ok": False,
            "tipo": "error",
            "mensaje": "El funcionario está inactivo."
        }

    if not funcionario.turno:
        return {
            "ok": False,
            "tipo": "error",
            "mensaje": "El funcionario no tiene un turno asignado."
        }

    asistencia, creada = Asistencia.objects.get_or_create(
        funcionario=funcionario,
        fecha=fecha_operativa
    )

    siguiente = asistencia.siguiente_marcacion

    if modo == "entrada":
        if siguiente == "entrada":
            asistencia.hora_entrada = ahora
            asistencia.origen_marcacion = origen
            asistencia.calcular_atraso()

            if asistencia.llego_tarde:
                asistencia.observacion = (
                    f"Llegó con {asistencia.minutos_atraso} minuto(s) de atraso. "
                    f"Entrada registrada por biométrico."
                )
            else:
                asistencia.observacion = "Entrada registrada en horario por biométrico."

            asistencia.save()

            registrar_historial(
                request,
                "Asistencia",
                "Entrada biométrica",
                f"Se registró entrada biométrica de {funcionario.nombre_completo} "
                f"a las {ahora.strftime('%H:%M:%S')}."
            )

            return {
                "ok": True,
                "tipo": "entrada",
                "mensaje": "Entrada registrada correctamente.",
                "subtipo": "Entrada del día",
                "hora": ahora.strftime("%H:%M:%S"),
                "llego_tarde": asistencia.llego_tarde,
                "minutos_atraso": asistencia.minutos_atraso,
                "turno": funcionario.turno.nombre,
            }

        if siguiente == "regreso_almuerzo":
            asistencia.hora_regreso_almuerzo = ahora
            asistencia.origen_marcacion = origen

            if asistencia.observacion:
                asistencia.observacion += " Regreso de almuerzo registrado por biométrico."
            else:
                asistencia.observacion = "Regreso de almuerzo registrado por biométrico."

            asistencia.save()

            registrar_historial(
                request,
                "Asistencia",
                "Regreso almuerzo biométrico",
                f"Se registró regreso de almuerzo biométrico de {funcionario.nombre_completo} "
                f"a las {ahora.strftime('%H:%M:%S')}."
            )

            return {
                "ok": True,
                "tipo": "regreso_almuerzo",
                "mensaje": "Regreso de almuerzo registrado correctamente.",
                "subtipo": "Vuelta de almuerzo",
                "hora": ahora.strftime("%H:%M:%S"),
                "llego_tarde": asistencia.llego_tarde,
                "minutos_atraso": asistencia.minutos_atraso,
                "turno": funcionario.turno.nombre,
            }

        if siguiente == "salida_almuerzo":
            return {
                "ok": False,
                "tipo": "espera_salida_almuerzo",
                "mensaje": "Aún corresponde registrar salida a almuerzo.",
                "hora_previa": asistencia.hora_entrada.strftime("%H:%M:%S") if asistencia.hora_entrada else None,
            }

        if siguiente == "salida":
            return {
                "ok": False,
                "tipo": "espera_salida_final",
                "mensaje": "Aún corresponde registrar salida final.",
                "hora_previa": asistencia.hora_entrada.strftime("%H:%M:%S") if asistencia.hora_entrada else None,
            }

        return {
            "ok": False,
            "tipo": "ya_completo",
            "mensaje": "El funcionario ya completó todas sus marcaciones del día.",
            "hora_previa": asistencia.hora_salida.strftime("%H:%M:%S") if asistencia.hora_salida else None,
        }

    if modo == "salida":
        if siguiente == "salida_almuerzo":
            asistencia.hora_salida_almuerzo = ahora
            asistencia.origen_marcacion = origen

            if asistencia.observacion:
                asistencia.observacion += " Salida a almuerzo registrada por biométrico."
            else:
                asistencia.observacion = "Salida a almuerzo registrada por biométrico."

            asistencia.save()

            registrar_historial(
                request,
                "Asistencia",
                "Salida almuerzo biométrica",
                f"Se registró salida a almuerzo biométrica de {funcionario.nombre_completo} "
                f"a las {ahora.strftime('%H:%M:%S')}."
            )

            return {
                "ok": True,
                "tipo": "salida_almuerzo",
                "mensaje": "Salida a almuerzo registrada correctamente.",
                "subtipo": "Inicio de almuerzo",
                "hora": ahora.strftime("%H:%M:%S"),
                "llego_tarde": asistencia.llego_tarde,
                "minutos_atraso": asistencia.minutos_atraso,
                "turno": funcionario.turno.nombre,
            }

        if siguiente == "salida":
            asistencia.hora_salida = ahora
            asistencia.origen_marcacion = origen

            if asistencia.observacion:
                asistencia.observacion += " Salida final registrada correctamente por biométrico."
            else:
                asistencia.observacion = "Salida final registrada correctamente por biométrico."

            asistencia.save()

            registrar_historial(
                request,
                "Asistencia",
                "Salida final biométrica",
                f"Se registró salida final biométrica de {funcionario.nombre_completo} "
                f"a las {ahora.strftime('%H:%M:%S')}."
            )

            return {
                "ok": True,
                "tipo": "salida",
                "mensaje": "Salida final registrada correctamente.",
                "subtipo": "Fin de jornada",
                "hora": ahora.strftime("%H:%M:%S"),
                "llego_tarde": asistencia.llego_tarde,
                "minutos_atraso": asistencia.minutos_atraso,
                "turno": funcionario.turno.nombre,
            }

        if siguiente == "entrada":
            return {
                "ok": False,
                "tipo": "sin_entrada",
                "mensaje": "Primero debe registrar entrada."
            }

        if siguiente == "regreso_almuerzo":
            return {
                "ok": False,
                "tipo": "espera_regreso_almuerzo",
                "mensaje": "Antes de salir debe registrar regreso de almuerzo.",
                "hora_previa": asistencia.hora_salida_almuerzo.strftime("%H:%M:%S") if asistencia.hora_salida_almuerzo else None,
            }

        return {
            "ok": False,
            "tipo": "ya_completo",
            "mensaje": "El funcionario ya completó todas sus marcaciones del día.",
            "hora_previa": asistencia.hora_salida.strftime("%H:%M:%S") if asistencia.hora_salida else None,
        }

    return {
        "ok": False,
        "tipo": "error",
        "mensaje": "No fue posible procesar la marcación."
    }


# =====================================================
# VISTAS
# =====================================================
@login_required
def biometrico_inicio(request):
    if not _tiene_permiso_biometrico(request, "puede_ver"):
        messages.error(request, "No tienes permiso para acceder al módulo biométrico.")
        return redirect("dashboard")

    empresa, empresas = _empresa_biometrica_seleccionada(request)
    funcionarios_base = _funcionarios_biometricos_base(empresa)
    total_funcionarios = funcionarios_base.count()
    con_rostro = funcionarios_base.filter(face_encoding__isnull=False).count()
    pendientes = funcionarios_base.filter(face_encoding__isnull=True).count()

    funcionarios_pendientes = funcionarios_base.filter(
        face_encoding__isnull=True
    ).order_by("apellido", "nombre")[:10]

    return render(request, "biometrico/inicio.html", {
        "total_funcionarios": total_funcionarios,
        "con_rostro": con_rostro,
        "pendientes": pendientes,
        "funcionarios_pendientes": funcionarios_pendientes,
        "empresa_seleccionada": empresa,
        "empresas_permitidas": empresas,
    })


@login_required
def rostros_pendientes(request):
    if not _tiene_permiso_biometrico(request, "puede_ver"):
        messages.error(request, "No tienes permiso para ver rostros pendientes.")
        return redirect("dashboard")

    empresa, empresas = _empresa_biometrica_seleccionada(request)
    if not empresa:
        messages.error(request, "No tienes acceso a la empresa solicitada.")
        return redirect("biometrico_inicio")

    sucursal_id = request.GET.get("sucursal") or ""
    sector = (request.GET.get("sector") or "").strip()
    busqueda = (request.GET.get("q") or "").strip()

    funcionarios_base = _funcionarios_biometricos_base(empresa)
    total_funcionarios = funcionarios_base.count()
    registrados = funcionarios_base.filter(face_encoding__isnull=False).count()
    pendientes_total = funcionarios_base.filter(face_encoding__isnull=True).count()
    cobertura = round((registrados / total_funcionarios) * 100) if total_funcionarios else 0

    pendientes_qs = funcionarios_base.filter(face_encoding__isnull=True)

    if sucursal_id:
        pendientes_qs = pendientes_qs.filter(sucursal_rel_id=sucursal_id)

    if sector:
        pendientes_qs = pendientes_qs.filter(sector=sector)

    if busqueda:
        pendientes_qs = pendientes_qs.filter(
            Q(nombre__icontains=busqueda)
            | Q(apellido__icontains=busqueda)
            | Q(cedula__icontains=busqueda)
        )

    funcionarios_pendientes = pendientes_qs.order_by("apellido", "nombre")[:250]
    pendientes_filtrados = pendientes_qs.count()
    sucursales = Sucursal.objects.filter(empresa=empresa, activo=True).order_by("nombre")
    sectores = funcionarios_base.exclude(sector="").values_list("sector", flat=True).distinct().order_by("sector")

    query_retorno = request.GET.urlencode()

    return render(request, "biometrico/rostros_pendientes.html", {
        "empresa_seleccionada": empresa,
        "empresas_permitidas": empresas,
        "sucursales": sucursales,
        "sectores": sectores,
        "funcionarios_pendientes": funcionarios_pendientes,
        "total_funcionarios": total_funcionarios,
        "registrados": registrados,
        "pendientes_total": pendientes_total,
        "pendientes_filtrados": pendientes_filtrados,
        "cobertura": cobertura,
        "sucursal_id": str(sucursal_id),
        "sector_sel": sector,
        "busqueda": busqueda,
        "query_retorno": query_retorno,
    })


def kiosko(request):
    return render(request, "biometrico/kiosko.html")


def kiosko_celular(request):
    return render(request, "biometrico/kiosko_celular.html")


@login_required
def laboratorio_offline(request):
    if not _permitir_laboratorio_offline(request):
        return JsonResponse({"ok": False, "error": "Acceso restringido."}, status=403)

    total_descriptores = Funcionario.objects.filter(
        activo=True,
        face_encoding__isnull=False,
    ).count()
    total_sin_foto = Funcionario.objects.filter(
        activo=True,
        foto="",
    ).count()

    return render(request, "biometrico/laboratorio_offline.html", {
        "total_descriptores": total_descriptores,
        "total_sin_foto": total_sin_foto,
        "debug_activo": settings.DEBUG,
    })


@login_required
def laboratorio_offline_descriptores(request):
    if not _permitir_laboratorio_offline(request):
        return JsonResponse({"ok": False, "error": "Acceso restringido."}, status=403)

    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Metodo no permitido."}, status=405)

    try:
        limite = int(request.GET.get("limite", 10) or 10)
    except (TypeError, ValueError):
        limite = 10
    limite = min(max(limite, 1), 10)
    funcionarios = Funcionario.objects.filter(
        activo=True,
        face_encoding__isnull=False,
    ).only("id", "face_encoding", "activo").order_by("id")[:limite]

    descriptores = []
    for funcionario in funcionarios:
        try:
            descriptor = np.frombuffer(funcionario.face_encoding, dtype=np.float64)
            if descriptor.shape[0] != 128:
                continue
            descriptor_js = descriptor.astype(np.float32)

            descriptores.append({
                "token": _token_laboratorio_funcionario(funcionario.id),
                "activo": bool(funcionario.activo),
                "modelo_generador": "dlib_face_recognition",
                "version_descriptor": "dlib-128-float64",
                "dimension": int(descriptor.shape[0]),
                "tipo_numerico_origen": "float64",
                "tipo_numerico_transporte": "float32",
                "endianess_origen": "native_numpy",
                "bytes": int(len(funcionario.face_encoding or b"")),
                "descriptor": [float(valor) for valor in descriptor_js.tolist()],
            })
        except Exception:
            continue

    logger.info(
        "Laboratorio offline Fase 0: muestra de descriptores solicitada por usuario=%s cantidad=%s",
        request.user.pk,
        len(descriptores),
    )

    return JsonResponse({
        "ok": True,
        "fase": "0",
        "uso": "laboratorio_offline_solo_lectura",
        "contiene_datos_biometricos": True,
        "limite": limite,
        "cantidad": len(descriptores),
        "descriptores": descriptores,
        "advertencia": "Datos anonimizados para PoC. No registrar asistencias ni almacenar en informes.",
    })


@login_required
def laboratorio_offline_sw(request):
    if not _permitir_laboratorio_offline(request):
        return HttpResponse("// Acceso restringido.", status=403, content_type="application/javascript")

    assets = [
        "/biometrico/laboratorio-offline/",
        "/static/css/biometrico_laboratorio_offline.css",
        "/static/js/biometrico_laboratorio_offline.js",
        "/static/biometrico_offline/vendor/face-api.js/dist/face-api.min.js",
        "/static/biometrico_offline/models/face-api/tiny_face_detector_model-weights_manifest.json",
        "/static/biometrico_offline/models/face-api/tiny_face_detector_model-shard1",
        "/static/biometrico_offline/models/face-api/face_landmark_68_model-weights_manifest.json",
        "/static/biometrico_offline/models/face-api/face_landmark_68_model-shard1",
        "/static/biometrico_offline/models/face-api/face_recognition_model-weights_manifest.json",
        "/static/biometrico_offline/models/face-api/face_recognition_model-shard1",
        "/static/biometrico_offline/models/face-api/face_recognition_model-shard2",
    ]
    contenido = f"""
const CACHE_NAME = "clockin-biometrico-lab-fase0-v3";
const LAB_ASSETS = {json.dumps(assets)};

self.addEventListener("install", (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(LAB_ASSETS))
  );
  self.skipWaiting();
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith("clockin-biometrico-lab-") && key !== CACHE_NAME)
        .map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
}});

self.addEventListener("fetch", (event) => {{
  const url = new URL(event.request.url);
  const esLaboratorio = url.pathname === "/biometrico/laboratorio-offline/" ||
    url.pathname === "/biometrico/laboratorio-offline/sw.js" ||
    url.pathname === "/static/css/biometrico_laboratorio_offline.css" ||
    url.pathname === "/static/js/biometrico_laboratorio_offline.js" ||
    url.pathname === "/static/biometrico_offline/vendor/face-api.js/dist/face-api.min.js" ||
    url.pathname.startsWith("/static/biometrico_offline/models/face-api/");

  if (!esLaboratorio || event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cached) => {{
      return cached || fetch(event.request).then((response) => {{
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      }});
    }})
  );
}});
"""
    return HttpResponse(contenido, content_type="application/javascript")


@login_required
@csrf_exempt
def registrar_rostro(request, funcionario_id):
    if not _tiene_permiso_biometrico(request, "puede_editar"):
        if request.method == "POST":
            return JsonResponse({"ok": False, "error": "No tienes permiso para registrar rostros."}, status=403)
        messages.error(request, "No tienes permiso para registrar rostros.")
        return redirect("biometrico_inicio")

    funcionario = get_object_or_404(
        Funcionario.objects.select_related("sucursal_rel", "sucursal_rel__empresa", "turno"),
        id=funcionario_id,
    )
    empresa_funcionario = funcionario.empresa
    empresas_permitidas = _empresas_biometricas_permitidas(request)
    if not empresa_funcionario or not empresas_permitidas.filter(pk=empresa_funcionario.pk).exists():
        if request.method == "POST":
            return JsonResponse({"ok": False, "error": "No puedes registrar rostros de otra empresa."}, status=403)
        messages.error(request, "No puedes registrar rostros de otra empresa.")
        return redirect("biometrico_inicio")

    retorno = request.GET.get("next") or request.POST.get("next") or ""
    if not retorno.startswith("/biometrico/rostros-pendientes/"):
        retorno = f"/biometrico/rostros-pendientes/?empresa={empresa_funcionario.pk}"

    rostro_existente = _descriptor_facial_valido(funcionario)
    actualizar = request.GET.get("actualizar") == "1" or request.POST.get("actualizar") == "1"

    if request.method == "GET":
        return render(request, "biometrico/registrar_rostro.html", {
            "funcionario": funcionario,
            "empresa": empresa_funcionario,
            "retorno": retorno,
            "rostro_existente": rostro_existente,
            "actualizar": actualizar,
        })

    if request.method == "POST":
        if rostro_existente and not actualizar:
            return JsonResponse({
                "ok": False,
                "tipo": "ya_registrado",
                "error": "Este funcionario ya tiene rostro registrado. Use Actualizar rostro para reemplazarlo.",
            })

        data = request.POST.get("imagen")
        origen = request.POST.get("origen", "CAMARA").strip().upper()
        accion = request.POST.get("accion", "guardar").strip().lower()

        try:
            resultado = _procesar_registro_rostro(funcionario, data, origen=origen, guardar=accion != "validar")
            if not resultado.get("ok"):
                return JsonResponse(resultado)

            if accion == "validar":
                return JsonResponse({
                    "ok": True,
                    "tipo": "rostro_valido",
                    "mensaje": "Rostro detectado correctamente.",
                })

            registrar_historial(
                request,
                "Biométrico",
                "Actualizar rostro" if resultado.get("era_actualizacion") else "Registrar rostro",
                (
                    f"Se {'actualizó' if resultado.get('era_actualizacion') else 'registró'} el rostro de "
                    f"{funcionario.nombre_completo}. Empresa: {empresa_funcionario.nombre}. "
                    f"Sucursal: {funcionario.sucursal_rel.nombre if funcionario.sucursal_rel else '-'}. "
                    f"Origen: {resultado.get('origen')}."
                )
            )

            return JsonResponse({
                "ok": True,
                "mensaje": resultado.get("mensaje"),
                "funcionario": funcionario.nombre_completo,
                "retorno": retorno,
                "tipo": resultado.get("tipo"),
            })

        except Exception as e:
            return JsonResponse({"ok": False, "tipo": "error", "error": _mensaje_error_amigable(str(e))})

    return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)


@csrf_exempt
def reconocimiento(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"})

    data = request.POST.get("imagen")
    modo = request.POST.get("modo", "entrada").strip().lower()
    origen = request.POST.get("origen", "biometrico_tablet").strip().lower()
    solo_deteccion = request.POST.get("solo_deteccion", "0").strip() in ["1", "true", "True"]

    if not data:
        return JsonResponse({"ok": False, "error": "No se recibió imagen"})

    try:
        frame = _base64_a_frame(data)

        if frame is None:
            return JsonResponse({
                "ok": False,
                "tipo": "error_imagen",
                "result_code": "TECHNICAL_ERROR",
                "mensaje": "No se pudo procesar la imagen."
            })

        analisis = _analizar_frame_basico(frame)
        hay_rostro = analisis.get("hay_rostro", False)
        cantidad_rostros = analisis.get("cantidad_rostros", 0)

        if solo_deteccion:
            return JsonResponse({
                "ok": True,
                "tipo": analisis.get("tipo", "deteccion"),
                "hay_rostro": hay_rostro,
                "cantidad_rostros": cantidad_rostros,
                "mensaje": analisis.get("mensaje", ""),
            })

        if not _controlar_frecuencia_backend():
            return JsonResponse({
                "ok": False,
                "tipo": "procesando",
                "result_code": "COOLDOWN",
                "mensaje": "Procesando lectura anterior."
            })

        if not hay_rostro:
            return JsonResponse({
                "ok": False,
                "tipo": analisis.get("tipo", "sin_rostro"),
                "result_code": "FACE_NOT_RECOGNIZED",
                "mensaje": analisis.get("mensaje", "Esperando rostro frente a cámara.")
            })

        if cantidad_rostros > 1:
            return JsonResponse({
                "ok": False,
                "tipo": "multiples_rostros",
                "result_code": "TECHNICAL_ERROR",
                "mensaje": "Hay más de un rostro frente a la cámara."
            })

        if analisis.get("tipo") in [
            "luz_baja",
            "posicion_izquierda",
            "posicion_derecha",
            "posicion_arriba",
            "posicion_abajo",
            "muy_lejos",
            "muy_cerca",
        ]:
            return JsonResponse({
                "ok": False,
                "tipo": analisis.get("tipo"),
                "result_code": "TECHNICAL_ERROR",
                "mensaje": analisis.get("mensaje"),
            })

        image_np = _base64_a_rgb_np(data)

        if image_np is None:
            return JsonResponse({
                "ok": False,
                "tipo": "error_imagen",
                "result_code": "TECHNICAL_ERROR",
                "mensaje": "No se pudo leer la imagen capturada."
            })

        funcionario, error, tipo_error = _reconocer_desde_imagen(image_np)

        if not funcionario:
            return JsonResponse({
                "ok": False,
                "tipo": tipo_error or "no_reconocido",
                "result_code": "FACE_NOT_RECOGNIZED",
                "mensaje": error or "Rostro detectado, pero no fue reconocido."
            })

        if not _bloqueo_por_rostro(funcionario.id):
            return JsonResponse({
                "ok": False,
                "tipo": "duplicado",
                "result_code": "COOLDOWN",
                "funcionario_id": funcionario.id,
                "funcionario": funcionario.nombre_completo,
                "mensaje": "Lectura reciente detectada. Espere unos segundos."
            })

        resultado = _marcar_asistencia_biometrica(request, funcionario, modo, origen=origen)
        result_code = _codigo_resultado_biometrico(resultado, modo)

        return JsonResponse({
            "ok": resultado["ok"],
            "tipo": resultado.get("tipo"),
            "result_code": result_code,
            "subtipo": resultado.get("subtipo"),
            "funcionario_id": funcionario.id,
            "funcionario": funcionario.nombre_completo,
            "mensaje": resultado.get("mensaje"),
            "hora": resultado.get("hora"),
            "hora_previa": resultado.get("hora_previa"),
            "turno": resultado.get("turno"),
            "llego_tarde": resultado.get("llego_tarde", False),
            "minutos_atraso": resultado.get("minutos_atraso", 0),
            "modo": modo,
            "origen": origen,
        })

    except Exception as e:
        return JsonResponse({
            "ok": False,
            "tipo": "error_validacion",
            "result_code": "TECHNICAL_ERROR",
            "mensaje": _mensaje_error_amigable(str(e))
        })
