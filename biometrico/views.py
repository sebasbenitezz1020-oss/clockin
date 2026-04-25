import base64
from io import BytesIO

import cv2
import face_recognition
import numpy as np
from PIL import Image

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import Asistencia, Funcionario
from core.views import registrar_historial


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
def _marcar_asistencia_biometrica(request, funcionario, modo):
    hoy = timezone.localdate()
    ahora = timezone.localtime()

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
        fecha=hoy
    )

    siguiente = asistencia.siguiente_marcacion

    if modo == "entrada":
        if siguiente == "entrada":
            asistencia.hora_entrada = ahora
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
                "mensaje": "Aún corresponde registrar salida a almuerzo."
            }

        if siguiente == "salida":
            return {
                "ok": False,
                "tipo": "espera_salida_final",
                "mensaje": "Aún corresponde registrar salida final."
            }

        return {
            "ok": False,
            "tipo": "ya_completo",
            "mensaje": "El funcionario ya completó todas sus marcaciones del día."
        }

    if modo == "salida":
        if siguiente == "salida_almuerzo":
            asistencia.hora_salida_almuerzo = ahora

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
                "mensaje": "Antes de salir debe registrar regreso de almuerzo."
            }

        return {
            "ok": False,
            "tipo": "ya_completo",
            "mensaje": "El funcionario ya completó todas sus marcaciones del día."
        }

    return {
        "ok": False,
        "tipo": "error",
        "mensaje": "No fue posible procesar la marcación."
    }


# =====================================================
# VISTAS
# =====================================================
def biometrico_inicio(request):
    total_funcionarios = Funcionario.objects.filter(activo=True).count()
    con_rostro = Funcionario.objects.filter(activo=True, face_encoding__isnull=False).count()
    pendientes = Funcionario.objects.filter(activo=True, face_encoding__isnull=True).count()

    funcionarios_pendientes = Funcionario.objects.filter(
        activo=True,
        face_encoding__isnull=True
    ).select_related("turno").order_by("apellido", "nombre")[:10]

    return render(request, "biometrico/inicio.html", {
        "total_funcionarios": total_funcionarios,
        "con_rostro": con_rostro,
        "pendientes": pendientes,
        "funcionarios_pendientes": funcionarios_pendientes,
    })


def kiosko(request):
    return render(request, "biometrico/kiosko.html")


@csrf_exempt
def registrar_rostro(request, funcionario_id):
    funcionario = get_object_or_404(Funcionario, id=funcionario_id)

    if request.method == "GET":
        return render(request, "biometrico/registrar_rostro.html", {
            "funcionario": funcionario
        })

    if request.method == "POST":
        data = request.POST.get("imagen")

        if not data:
            return JsonResponse({"ok": False, "error": "No se recibió imagen"})

        try:
            image_np = _base64_a_rgb_np(data)

            if image_np is None:
                return JsonResponse({
                    "ok": False,
                    "error": "No se pudo procesar la imagen."
                })

            ok_luz, tipo_luz, mensaje_luz = _validar_iluminacion(image_np)
            if not ok_luz:
                return JsonResponse({
                    "ok": False,
                    "error": mensaje_luz,
                    "tipo": tipo_luz,
                })

            small = cv2.resize(image_np, (0, 0), fx=0.65, fy=0.65)

            face_locations = face_recognition.face_locations(small, model="hog")

            if not face_locations:
                return JsonResponse({
                    "ok": False,
                    "error": "No se detectó rostro. Colóquese de frente a la cámara."
                })

            if len(face_locations) > 1:
                return JsonResponse({
                    "ok": False,
                    "error": "Se detectaron varios rostros. Debe registrarse una sola persona."
                })

            encodings = face_recognition.face_encodings(small, face_locations)

            if not encodings:
                return JsonResponse({
                    "ok": False,
                    "error": "No se pudo generar el registro facial. Intente con mejor iluminación."
                })

            encoding = encodings[0]
            funcionario.face_encoding = encoding.tobytes()
            funcionario.save()

            _limpiar_cache_rostros()

            registrar_historial(
                request,
                "Biométrico",
                "Registrar rostro",
                f"Se registró/actualizó el rostro de {funcionario.nombre_completo}."
            )

            return JsonResponse({
                "ok": True,
                "mensaje": f"Rostro guardado para {funcionario.nombre_completo}"
            })

        except Exception as e:
            return JsonResponse({"ok": False, "error": _mensaje_error_amigable(str(e))})

    return JsonResponse({"ok": False, "error": "Método no permitido"})


@csrf_exempt
def reconocimiento(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"})

    data = request.POST.get("imagen")
    modo = request.POST.get("modo", "entrada").strip().lower()
    solo_deteccion = request.POST.get("solo_deteccion", "0").strip() in ["1", "true", "True"]

    if not data:
        return JsonResponse({"ok": False, "error": "No se recibió imagen"})

    try:
        frame = _base64_a_frame(data)

        if frame is None:
            return JsonResponse({
                "ok": False,
                "tipo": "error_imagen",
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
                "mensaje": "Procesando lectura anterior."
            })

        if not hay_rostro:
            return JsonResponse({
                "ok": False,
                "tipo": analisis.get("tipo", "sin_rostro"),
                "mensaje": analisis.get("mensaje", "Esperando rostro frente a cámara.")
            })

        if cantidad_rostros > 1:
            return JsonResponse({
                "ok": False,
                "tipo": "multiples_rostros",
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
                "mensaje": analisis.get("mensaje"),
            })

        image_np = _base64_a_rgb_np(data)

        if image_np is None:
            return JsonResponse({
                "ok": False,
                "tipo": "error_imagen",
                "mensaje": "No se pudo leer la imagen capturada."
            })

        funcionario, error, tipo_error = _reconocer_desde_imagen(image_np)

        if not funcionario:
            return JsonResponse({
                "ok": False,
                "tipo": tipo_error or "no_reconocido",
                "mensaje": error or "Rostro detectado, pero no fue reconocido."
            })

        if not _bloqueo_por_rostro(funcionario.id):
            return JsonResponse({
                "ok": False,
                "tipo": "duplicado",
                "funcionario_id": funcionario.id,
                "funcionario": funcionario.nombre_completo,
                "mensaje": "Lectura reciente detectada. Espere unos segundos."
            })

        resultado = _marcar_asistencia_biometrica(request, funcionario, modo)

        return JsonResponse({
            "ok": resultado["ok"],
            "tipo": resultado.get("tipo"),
            "subtipo": resultado.get("subtipo"),
            "funcionario_id": funcionario.id,
            "funcionario": funcionario.nombre_completo,
            "mensaje": resultado.get("mensaje"),
            "hora": resultado.get("hora"),
            "turno": resultado.get("turno"),
            "llego_tarde": resultado.get("llego_tarde", False),
            "minutos_atraso": resultado.get("minutos_atraso", 0),
            "modo": modo,
        })

    except Exception as e:
        return JsonResponse({
            "ok": False,
            "tipo": "error_validacion",
            "mensaje": _mensaje_error_amigable(str(e))
        })