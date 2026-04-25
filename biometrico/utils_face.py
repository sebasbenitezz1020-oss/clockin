import cv2
import face_recognition
import numpy as np

from core.models import Funcionario


TOLERANCIA_RECONOCIMIENTO = 0.60

_CACHE_ENCODINGS = {
    "cantidad": None,
    "encodings": None,
    "funcionarios": None,
}


def limpiar_cache_encodings():
    _CACHE_ENCODINGS["cantidad"] = None
    _CACHE_ENCODINGS["encodings"] = None
    _CACHE_ENCODINGS["funcionarios"] = None


def obtener_encodings(usar_cache=True):
    funcionarios_db = Funcionario.objects.filter(
        activo=True,
        face_encoding__isnull=False,
    ).only(
        "id",
        "nombre",
        "apellido",
        "cedula",
        "activo",
        "face_encoding",
    )

    cantidad_actual = funcionarios_db.count()

    if (
        usar_cache
        and _CACHE_ENCODINGS["encodings"] is not None
        and _CACHE_ENCODINGS["funcionarios"] is not None
        and _CACHE_ENCODINGS["cantidad"] == cantidad_actual
    ):
        return _CACHE_ENCODINGS["encodings"], _CACHE_ENCODINGS["funcionarios"]

    encodings = []
    funcionarios = []

    for funcionario in funcionarios_db:
        if not funcionario.face_encoding:
            continue

        try:
            encoding = np.frombuffer(funcionario.face_encoding, dtype=np.float64)

            if encoding.shape[0] != 128:
                continue

            encodings.append(encoding)
            funcionarios.append(funcionario)

        except Exception:
            continue

    _CACHE_ENCODINGS["cantidad"] = cantidad_actual
    _CACHE_ENCODINGS["encodings"] = encodings
    _CACHE_ENCODINGS["funcionarios"] = funcionarios

    return encodings, funcionarios


def _preparar_imagen(imagen):
    """
    Acepta:
    - ruta de archivo
    - imagen numpy RGB
    - imagen numpy BGR
    """

    if isinstance(imagen, str):
        return face_recognition.load_image_file(imagen)

    if isinstance(imagen, np.ndarray):
        img = imagen

        if len(img.shape) != 3:
            return None

        if img.shape[2] == 3:
            return img

    return None


def reconocer(imagen, tolerance=TOLERANCIA_RECONOCIMIENTO):
    imagen_np = _preparar_imagen(imagen)

    if imagen_np is None:
        return None

    try:
        if imagen_np.shape[1] > 720:
            scale = 720 / imagen_np.shape[1]
            imagen_np = cv2.resize(
                imagen_np,
                (720, int(imagen_np.shape[0] * scale)),
                interpolation=cv2.INTER_AREA,
            )

        ubicaciones = face_recognition.face_locations(imagen_np, model="hog")

        if not ubicaciones:
            return None

        if len(ubicaciones) > 1:
            return None

        encodings = face_recognition.face_encodings(imagen_np, ubicaciones)

        if not encodings:
            return None

        encoding_actual = encodings[0]

        conocidos, funcionarios = obtener_encodings()

        if not conocidos:
            return None

        distancias = face_recognition.face_distance(conocidos, encoding_actual)

        if len(distancias) == 0:
            return None

        mejor_indice = int(np.argmin(distancias))
        mejor_distancia = float(distancias[mejor_indice])

        if mejor_distancia <= tolerance:
            return funcionarios[mejor_indice]

        return None

    except Exception:
        return None