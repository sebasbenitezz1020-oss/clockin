# ClockIn Web - Biometrico Offline Fase 0

## Objetivo

Evaluar si el modulo biometrico de ClockIn puede evolucionar a funcionamiento offline mediante PWA o aplicacion web instalada, reutilizando en lo posible los rostros ya registrados.

Esta fase no modifica el lector de tablet, no modifica el lector de celular, no registra asistencias reales y no altera datos biometricos existentes.

## Arquitectura biometrica actual

El reconocimiento actual se ejecuta en el servidor Django.

Flujo actual:

```text
Camara del navegador
-> captura JPEG/base64 con canvas
-> POST a /biometrico/reconocer/
-> Django decodifica la imagen
-> OpenCV valida frame, brillo y posicion
-> face_recognition/dlib detecta rostro
-> face_recognition/dlib genera embedding 128D
-> comparacion contra Funcionario.face_encoding
-> identificacion del funcionario
-> registro de Asistencia
```

## Archivos involucrados

- `biometrico/views.py`: motor principal de reconocimiento, registro facial, deteccion, comparacion y marcacion.
- `biometrico/utils_face.py`: utilidades de reconocimiento facial con cache de encodings.
- `biometrico/urls.py`: rutas del modulo biometrico.
- `biometrico/templates/biometrico/kiosko.html`: lector actual para tablet/notebook/punto fijo.
- `biometrico/templates/biometrico/kiosko_celular.html`: lector actual optimizado para celular.
- `biometrico/templates/biometrico/registrar_rostro.html`: captura para registrar rostro.
- `core/models.py`: `Funcionario.face_encoding`, `Funcionario.foto`, `Asistencia.origen_marcacion`, configuracion biometrica.
- `templates/base.html`: manifest PWA basico.
- `static/img/clockin/site.webmanifest`: manifest PWA actual.
- `requirements.txt`: dependencias del motor servidor.

## Dependencias actuales

- `face-recognition==1.3.0`
- `face_recognition_models==0.3.0`
- `dlib==20.0.1`
- `opencv-python==4.13.0.92`
- `numpy==2.2.6`
- `Pillow==12.2.0`

## Ubicacion del reconocimiento

El navegador no genera el embedding facial. El navegador captura una imagen y la envia al servidor. El servidor realiza:

- conversion base64 a imagen;
- deteccion de rostro;
- generacion de descriptor;
- comparacion contra descriptores guardados;
- registro de asistencia cuando corresponde.

Funciones principales:

- `_base64_a_frame`
- `_base64_a_rgb_np`
- `_analizar_frame_basico`
- `_reconocer_desde_imagen`
- `_marcar_asistencia_biometrica`
- `reconocimiento`
- `registrar_rostro`

## Almacenamiento actual

El modelo `Funcionario` contiene:

- `face_encoding`: `BinaryField`, descriptor facial.
- `foto`: `ImageField`, fotografia de funcionario si fue cargada por ficha.

Los descriptores actuales tienen formato observado:

- 128 dimensiones;
- `float64`;
- 1024 bytes por descriptor;
- generados por `dlib/face_recognition`.

No se debe asumir que estos descriptores son compatibles con un motor web diferente.

## PWA actual

ClockIn cuenta con manifest basico:

- `display: standalone`;
- iconos PWA;
- `theme_color`;
- `background_color`;
- meta tags moviles.

No se encontro service worker principal activo, estrategia de cache offline, IndexedDB biometrico ni modelos faciales web locales.

## Laboratorio creado

Ruta:

- `/biometrico/laboratorio-offline/`

Rutas auxiliares:

- `/biometrico/laboratorio-offline/descriptores/`
- `/biometrico/laboratorio-offline/sw.js`

Proteccion:

- requiere usuario autenticado;
- permite superusuario;
- permite entorno `DEBUG=True`;
- no aparece en el menu principal;
- no registra asistencias;
- no modifica funcionarios;
- no modifica descriptores.

## Motor facial web seleccionado

Motor incorporado para la PoC:

- nombre: `face-api.js`;
- version: `0.22.2`;
- licencia: MIT;
- ubicacion local: `static/biometrico_offline/vendor/face-api.js/`;
- archivo de ejecucion: `static/biometrico_offline/vendor/face-api.js/dist/face-api.min.js`;
- dependencia base: TensorFlow.js incluido en el bundle distribuido;
- backend observado en navegador: lo informa el laboratorio mediante `faceapi.tf.getBackend()`;
- genera embeddings de 128 dimensiones mediante `faceRecognitionNet`;
- no se carga desde CDN.

Motivo de seleccion:

- permite deteccion, landmarks, alineacion y descriptor en navegador;
- la documentacion del paquete indica que su red de reconocimiento es equivalente a `FaceRecognizerNet` y al ejemplo de reconocimiento facial de dlib;
- produce descriptores de 128 valores, aunque la compatibilidad numerica debe validarse con capturas reales.

Comparativa inicial:

| Motor | Embeddings | Backend | Riesgo principal |
| --- | --- | --- | --- |
| face-api.js | Si | TensorFlow.js / CPU/WebGL segun navegador | Debe validarse equivalencia numerica con dlib actual |
| TensorFlow.js + modelo facial | Si, segun modelo | WebGL / WASM / CPU | Requiere elegir y versionar modelo |
| ONNX Runtime Web + ArcFace/FaceNet | Si | WASM / WebGL/WebGPU segun soporte | Requiere pipeline completo local |
| MediaPipe | Principalmente deteccion/landmarks | WebGL/WASM | No resuelve por si solo reconocimiento comparable |

## Recursos locales incorporados

Ubicacion:

- `static/biometrico_offline/vendor/`
- `static/biometrico_offline/models/face-api/`

Inventario SHA-256:

| Archivo | Tamano aprox. | SHA-256 |
| --- | ---: | --- |
| `face-api.js-0.22.2.tgz` | 4.9 MB paquete | `DB4D2C5D08957CF761B092DE2DF733AB4C8AD7D4D4E8906B7C6924A6ED0604DD` |
| `face-api.min.js` | 664 KB | `5D66EC95338D7FCC365CE15481B8599BAF4B6E22C9A624B76D4CA821A669A659` |
| `tiny_face_detector_model-weights_manifest.json` | 2.9 KB | `14C60659A31B6B7B1320077171B8F8ADCB24EF0E62DDE62CE603BCB49A1B49B5` |
| `tiny_face_detector_model-shard1` | 193 KB | `B7503CE7DF31039B1C43316A9B865CAB6A70DD748CC602D3FA28B551503C3871` |
| `face_landmark_68_model-weights_manifest.json` | 7.9 KB | `D30F6CC341009EA4F8223876959289B96576FC54A2615F92DA9741AB9C5F0BBC` |
| `face_landmark_68_model-shard1` | 357 KB | `4611EF65C87D836D03D684B30EEC4D195D8B219FA1DD58FC58945831C6B9299B` |
| `face_recognition_model-weights_manifest.json` | 18 KB | `6619F4126F845C1F7857F39CBD79565F375734F46E0DD25D9602F8DC21CDA9F5` |
| `face_recognition_model-shard1` | 4.0 MB | `412566A2B8D814D84C60B8055EC5D3B3B2328EF7CD7853384E03EC3DB7B053D8` |
| `face_recognition_model-shard2` | 2.1 MB | `69350FDECD845C532E44DD8F7D0521C773505EF46B87CC34F46640A0CC334ECC` |

Procedencia:

- paquete npm `face-api.js@0.22.2`;
- pesos oficiales del repositorio publico del proyecto `face-api.js`.

Nota legal: mantener este inventario antes de llevar a produccion. Si se decide redistribuir comercialmente, revisar nuevamente licencias de libreria, pesos y dependencias.

## Hipotesis a validar

1. La camara puede abrirse en modo PWA instalada.
2. El laboratorio puede cargar sin conexion tras cachearse.
3. IndexedDB soporta paquetes de 100 a 5.000 descriptores ficticios.
4. Los descriptores `dlib-128-float64` actuales no deben considerarse compatibles hasta comparar contra embeddings generados por `face-api.js` en navegador.
5. Si no hay fotografias existentes, los funcionarios cuyo descriptor sea incompatible requeriran nuevo registro.

## Riesgos detectados

- Exponer descriptores biometricos al navegador aumenta el riesgo de seguridad.
- Una PWA no tiene el mismo aislamiento que una app nativa.
- iOS limita almacenamiento, ejecucion en segundo plano y comportamiento de PWA.
- La camara offline depende de contexto seguro y permisos del navegador.
- Si el modelo web cambia, los descriptores deben versionarse.
- Si se cambia de motor, puede ser necesario regenerar embeddings.

## Criterios de exito de la PoC

- Cargar la ruta de laboratorio.
- Registrar service worker aislado para el laboratorio.
- Abrir camara.
- Medir captura local sin enviar imagen al servidor.
- Cargar muestra limitada de descriptores anonimizados.
- Generar embedding real en navegador con `face-api.js`.
- Comparar embedding web contra descriptores actuales de dlib.
- Guardar y leer descriptores ficticios en IndexedDB.
- Medir comparacion lineal con 10, 100, 500, 1.000 y 5.000 descriptores ficticios.
- Exportar metricas sin imagenes ni descriptores reales.
- Documentar si la compatibilidad con dlib queda confirmada, descartada o inconclusa.

## Decision inicial

Estado actual: **VIABLE CON LIMITACIONES - COMPATIBILIDAD PENDIENTE DE CAPTURAS REALES.**

La viabilidad del reconocimiento facial completamente offline ya cuenta con motor web local para prueba. Falta ejecutar capturas reales de la misma persona y de personas diferentes para cerrar si los descriptores `dlib` son compatibles directamente, compatibles con conversion o incompatibles.
