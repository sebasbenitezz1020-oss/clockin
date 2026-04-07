import base64
import os
import tempfile

import cv2
import face_recognition
import numpy as np
from PIL import Image
from io import BytesIO

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.models import Funcionario, Asistencia
from core.views import registrar_historial
from .utils_face import reconocer


# =========================
# ANTI FRAUDE BÁSICO
# =========================
ultimo_frame_gray = None
ultimo_tiempo_captura = None


def _base64_a_frame(data_url):
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return frame


def _detectar_movimiento(frame_actual):
    global ultimo_frame_gray

    gris_actual = cv2.cvtColor(frame_actual, cv2.COLOR_BGR2GRAY)
    gris_actual = cv2.GaussianBlur(gris_actual, (21, 21), 0)

    if ultimo_frame_gray is None:
        ultimo_frame_gray = gris_actual
        return True

    diff = cv2.absdiff(ultimo_frame_gray, gris_actual)
    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    movimiento = int(np.sum(thresh))

    ultimo_frame_gray = gris_actual

    return movimiento > 150000


def _controlar_tiempo():
    global ultimo_tiempo_captura

    ahora = timezone.now()

    if ultimo_tiempo_captura is None:
        ultimo_tiempo_captura = ahora
        return True

    diferencia = (ahora - ultimo_tiempo_captura).total_seconds()

    if diferencia < 2:
        return False

    ultimo_tiempo_captura = ahora
    return True


# =========================
# ASISTENCIA BIOMÉTRICA
# =========================
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

    if modo == "entrada":
        if not asistencia.hora_entrada:
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
                "hora": ahora.strftime("%H:%M:%S"),
                "llego_tarde": asistencia.llego_tarde,
                "minutos_atraso": asistencia.minutos_atraso,
                "turno": funcionario.turno.nombre,
            }

        if asistencia.hora_entrada and not asistencia.hora_salida:
            return {
                "ok": False,
                "tipo": "ya_entrada",
                "mensaje": "El funcionario ya registró su entrada hoy."
            }

        return {
            "ok": False,
            "tipo": "ya_completo",
            "mensaje": "El funcionario ya registró entrada y salida el día de hoy."
        }

    if not asistencia.hora_entrada:
        return {
            "ok": False,
            "tipo": "sin_entrada",
            "mensaje": "No se puede registrar salida porque aún no tiene entrada hoy."
        }

    if not asistencia.hora_salida:
        asistencia.hora_salida = ahora

        if asistencia.observacion:
            asistencia.observacion += " Salida registrada correctamente por biométrico."
        else:
            asistencia.observacion = "Salida registrada correctamente por biométrico."

        asistencia.save()

        registrar_historial(
            request,
            "Asistencia",
            "Salida biométrica",
            f"Se registró salida biométrica de {funcionario.nombre_completo} "
            f"a las {ahora.strftime('%H:%M:%S')}."
        )

        return {
            "ok": True,
            "tipo": "salida",
            "mensaje": "Salida registrada correctamente.",
            "hora": ahora.strftime("%H:%M:%S"),
            "llego_tarde": asistencia.llego_tarde,
            "minutos_atraso": asistencia.minutos_atraso,
            "turno": funcionario.turno.nombre,
        }

    return {
        "ok": False,
        "tipo": "ya_salida",
        "mensaje": "El funcionario ya registró su salida hoy."
    }


# =========================
# VISTAS
# =========================
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
            image_data = base64.b64decode(data.split(",")[1])
            image = Image.open(BytesIO(image_data)).convert("RGB")
            image_np = np.array(image)

            encodings = face_recognition.face_encodings(image_np)

            if not encodings:
                return JsonResponse({"ok": False, "error": "No se detectó rostro"})

            encoding = encodings[0]
            funcionario.face_encoding = encoding.tobytes()
            funcionario.save()

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
            return JsonResponse({"ok": False, "error": str(e)})

    return JsonResponse({"ok": False, "error": "Método no permitido"})


@csrf_exempt
def reconocimiento(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"})

    data = request.POST.get("imagen")
    modo = request.POST.get("modo", "entrada").strip().lower()

    if not data:
        return JsonResponse({"ok": False, "error": "No se recibió imagen"})

    temp_path = None

    try:
        if not _controlar_tiempo():
            return JsonResponse({
                "ok": False,
                "tipo": "anti_fraude",
                "error": "Captura demasiado rápida. Espere un momento."
            })

        frame = _base64_a_frame(data)
        if frame is None:
            return JsonResponse({
                "ok": False,
                "tipo": "anti_fraude",
                "error": "No se pudo procesar la imagen."
            })

        if not _detectar_movimiento(frame):
            return JsonResponse({
                "ok": False,
                "tipo": "anti_fraude",
                "error": "No se detecta movimiento suficiente. Posible intento de fraude."
            })

        image_data = base64.b64decode(data.split(",")[1])
        image = Image.open(BytesIO(image_data)).convert("RGB")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path, format="JPEG")

        funcionario = reconocer(temp_path)

        if not funcionario:
            return JsonResponse({
                "ok": False,
                "tipo": "no_reconocido",
                "error": "No reconocido"
            })

        resultado = _marcar_asistencia_biometrica(request, funcionario, modo)

        return JsonResponse({
            "ok": resultado["ok"],
            "tipo": resultado.get("tipo"),
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
        return JsonResponse({"ok": False, "error": str(e)})

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)