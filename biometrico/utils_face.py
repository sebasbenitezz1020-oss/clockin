import face_recognition
import numpy as np
from core.models import Funcionario


def obtener_encodings():
    encodings = []
    funcionarios = []

    funcionarios_db = Funcionario.objects.exclude(face_encoding__isnull=True)

    for f in funcionarios_db:
        if not f.face_encoding:
            continue

        try:
            encoding = np.frombuffer(f.face_encoding, dtype=np.float64)
            encodings.append(encoding)
            funcionarios.append(f)
        except Exception:
            continue

    return encodings, funcionarios


def reconocer(imagen_path):
    imagen = face_recognition.load_image_file(imagen_path)
    ubicaciones = face_recognition.face_locations(imagen)
    encodings = face_recognition.face_encodings(imagen, ubicaciones)

    if not encodings:
        return None

    encoding_actual = encodings[0]

    conocidos, funcionarios = obtener_encodings()

    if not conocidos:
        return None

    resultados = face_recognition.compare_faces(conocidos, encoding_actual, tolerance=0.5)
    distancias = face_recognition.face_distance(conocidos, encoding_actual)

    if True in resultados:
        mejor_indice = np.argmin(distancias)
        return funcionarios[mejor_indice]

    return None