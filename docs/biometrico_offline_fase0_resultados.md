# Resultados - Biometrico Offline Fase 0

## Estado de la PoC

Se creo un laboratorio aislado para investigacion offline:

- ruta: `/biometrico/laboratorio-offline/`;
- endpoint de muestra: `/biometrico/laboratorio-offline/descriptores/`;
- service worker aislado: `/biometrico/laboratorio-offline/sw.js`;
- CSS y JS locales;
- motor facial web local `face-api.js@0.22.2`;
- modelos locales de deteccion, landmarks y reconocimiento;
- sin CDN;
- sin registro de asistencias;
- sin modificaciones sobre funcionarios;
- sin cambios en los lectores productivos de tablet y celular.

## Resultado de arquitectura actual

El reconocimiento facial actual ocurre en el servidor. El navegador solo captura imagen y la envia a Django.

Decision tecnica: el lector actual no puede funcionar completamente offline sin incorporar un motor facial web o nativo.

## Muestra local revisada

Base de desarrollo revisada:

- funcionarios totales: 7;
- funcionarios activos: 7;
- funcionarios activos con descriptor: 5;
- fotografias de funcionario referenciadas: 0;
- tamano observado por descriptor: 1024 bytes;
- formato observado: 128 valores `float64`.

No se exportaron imagenes ni descriptores reales a este informe.

## Motor probado

- motor: `face-api.js`;
- version: `0.22.2`;
- licencia declarada: MIT;
- arquitectura de reconocimiento: `faceRecognitionNet`;
- dimension de embedding: 128;
- detector usado: `tinyFaceDetector`;
- landmarks: `faceLandmark68Net`;
- backend: informado en vivo por el navegador mediante TensorFlow.js.

El laboratorio permite generar el embedding completamente en el navegador y compararlo localmente contra una muestra anonima de descriptores dlib.

## Prueba critica de compatibilidad

Controles incorporados al laboratorio:

- `Generar embedding`: detecta un rostro unico y genera el embedding en navegador.
- `Cargar muestra`: recupera una muestra limitada y anonima desde el endpoint protegido.
- `Comparar contra descriptor A`: compara el embedding actual contra el primer descriptor dlib de la muestra.
- `Comparar contra descriptor B`: compara el embedding actual contra el segundo descriptor dlib de la muestra.

El laboratorio muestra solamente:

- dimension del embedding web;
- dimension del descriptor dlib;
- distancia euclidiana;
- similitud coseno;
- tiempo de generacion;
- tiempo de comparacion.

No muestra vectores, no guarda fotografias, no guarda embeddings en base de datos y no modifica `Funcionario.face_encoding`.

Metodologia para la prueba A/A, A/B, B/A, B/B:

1. Cargar modelo.
2. Iniciar camara.
3. Cargar muestra.
4. Colocar frente a camara a la persona correspondiente al descriptor A.
5. Presionar `Generar embedding`.
6. Presionar `Comparar contra descriptor A`.
7. Presionar `Comparar contra descriptor B`.
8. Repetir con la persona correspondiente al descriptor B.

Resultados pendientes de carga manual:

| Prueba | Distancia euclidiana | Similitud coseno | Resultado |
| --- | ---: | ---: | --- |
| A contra A | Pendiente | Pendiente | Pendiente |
| A contra B | Pendiente | Pendiente | Pendiente |
| B contra A | Pendiente | Pendiente | Pendiente |
| B contra B | Pendiente | Pendiente | Pendiente |

## Compatibilidad de embeddings

Resultado actual: **VIABLE CON LIMITACIONES - COMPATIBILIDAD PENDIENTE**.

Motivo:

- los descriptores existentes son `dlib/face_recognition`;
- se incorporo un motor web que tambien genera vectores de 128 dimensiones;
- falta ejecutar capturas reales de la misma persona y personas diferentes para medir separacion de distancias;
- no se debe asumir compatibilidad por dimension ni por arquitectura equivalente hasta medir.

Clasificacion inicial:

- descriptores actuales: reutilizables solo si el motor offline es compatible con `dlib-128-float64`;
- funcionarios sin fotografia guardada: si el descriptor no es compatible, requeririan nuevo registro;
- funcionarios sin descriptor: requieren registro.

## IndexedDB

El laboratorio permite ejecutar pruebas locales con datos ficticios:

- 10 descriptores;
- 100 descriptores;
- 500 descriptores;
- 1.000 descriptores;
- 5.000 descriptores.

Cada prueba mide:

- tiempo de escritura;
- tiempo de lectura;
- tiempo de comparacion lineal;
- tamano estimado;
- persistencia local hasta limpiar la base.

Los resultados concretos dependen del navegador y dispositivo donde se ejecute la prueba.

## Service Worker

Se creo un service worker experimental exclusivo para el laboratorio.

Alcance solicitado:

- `/biometrico/laboratorio-offline/`

Recursos cacheados:

- pagina del laboratorio;
- CSS del laboratorio;
- JS del laboratorio.
- `face-api.min.js`;
- manifiestos de modelos;
- shards de pesos de deteccion, landmarks y reconocimiento.

No intercepta rutas normales de ClockIn.

## Prueba offline

Procedimiento recomendado:

1. Ingresar a `/biometrico/laboratorio-offline/` con Internet.
2. Confirmar que el Service Worker figure como registrado.
3. Abrir la camara.
4. Cargar muestra limitada.
5. Ejecutar pruebas IndexedDB.
6. Desactivar Wi-Fi/datos.
7. Recargar la ruta del laboratorio.
8. Cargar el modelo facial local.
9. Confirmar que el laboratorio abre desde cache.
10. Confirmar estado "Offline".
11. Generar embedding en navegador.
12. Comparar contra muestra dlib sin consultar `/biometrico/reconocer/`.
13. Verificar que no se registra ninguna asistencia.

## Limitaciones Android

- Chrome/Edge soportan PWA, camara, IndexedDB y Service Worker en contexto seguro.
- El rendimiento depende de CPU, memoria y aceleracion WebGL/WASM.
- En dispositivos de gama media, comparar muchos descriptores de forma lineal puede afectar bateria y temperatura.

## Limitaciones iOS

- Safari/PWA tiene restricciones mas fuertes sobre almacenamiento y ejecucion en segundo plano.
- Los permisos de camara pueden variar si la app se ejecuta instalada.
- El espacio persistente puede ser purgado por el sistema.
- Background sync no debe considerarse garantizado.

## Seguridad

Riesgos:

- guardar descriptores biometricos en un dispositivo aumenta superficie de exposicion;
- una PWA puede ser inspeccionada con herramientas del navegador;
- sin cifrado local y autorizacion por dispositivo, no se recomienda descargar paquetes reales masivos.

Recomendacion futura:

- cifrado local con Web Crypto;
- claves por dispositivo autorizado;
- expiracion de paquetes;
- revocacion desde servidor;
- separacion por empresa/sucursal;
- no guardar fotografias si no son necesarias;
- versionado de modelo y descriptores.

## Decision sobre re-registro

Decision actual: **inconclusa hasta capturas reales**.

Escenarios:

- Si se mantiene un motor compatible con `dlib/face_recognition`, no seria necesario volver a registrar rostros con descriptor valido.
- Si se cambia a un motor web incompatible, sera necesario regenerar descriptores desde fotografias existentes.
- Si no existen fotografias guardadas y el descriptor actual es incompatible, esos funcionarios deberan registrar el rostro nuevamente.

## Decision final provisional

**VIABLE CON LIMITACIONES - COMPATIBILIDAD PENDIENTE**.

La PWA offline parece viable para interfaz, cache, camara, IndexedDB y carga de motor facial local. La compatibilidad real con descriptores dlib actuales depende de ejecutar la prueba de misma persona/personas diferentes desde el laboratorio.

## Plan recomendado para Fase 1

1. Elegir motor facial web local.
2. Incorporar modelos en archivos locales versionados.
3. Crear comparador real de embeddings en navegador.
4. Medir Android y iOS reales.
5. Definir si se reutilizan descriptores `dlib` o se regeneran.
6. Disenar paquete biometrico cifrado por empresa/sucursal.
