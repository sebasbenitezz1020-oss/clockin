(function () {
    "use strict";

    const shell = document.querySelector(".lab-shell");
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const detectionCanvas = document.getElementById("detectionCanvas");
    const logOutput = document.getElementById("logOutput");
    const indexedDbOutput = document.getElementById("indexedDbOutput");

    const DETECTOR_INPUT_SIZE = 416;
    const DETECTOR_SCORE_THRESHOLD = 0.35;
    const MIN_FACE_WIDTH_RATIO = 0.12;
    const MIN_FACE_HEIGHT_RATIO = 0.16;
    const MIN_DETECTION_INTERVAL_MS = 650;

    const state = {
        descriptors: [],
        descriptorA: null,
        descriptorB: null,
        currentEmbedding: null,
        currentEmbeddingMeta: null,
        sampleA: null,
        sampleB: null,
        modelLoaded: false,
        lastDetectionAt: 0,
        metrics: {
            fase: "0",
            motor_facial: "face-api.js",
            version_motor: "0.22.2",
            modelo_reconocimiento: "face_recognition_model",
            modelo_landmarks: "face_landmark_68_model",
            modelo_detector: "tiny_face_detector_model",
            backend: "tensorflowjs_browser",
            navegador: navigator.userAgent,
            online_inicial: navigator.onLine,
            service_worker: "pendiente",
            indexeddb: [],
            compatibilidad_embeddings: "PENDIENTE_PRUEBA_REAL",
            asistencia_registrada: false,
            observaciones: [
                "Laboratorio aislado: no registra asistencias.",
                "No se guardan imagenes ni descriptores reales en informes.",
                "Los vectores completos no se imprimen en consola ni se exportan.",
            ],
        },
    };

    function $(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const node = $(id);
        if (node) node.textContent = value;
    }

    function nowMs() {
        return performance.now();
    }

    function log(message) {
        const stamp = new Date().toLocaleTimeString();
        logOutput.textContent += `\n[${stamp}] ${message}`;
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    function clearDetectionOverlay() {
        if (!detectionCanvas) return;
        const ctx = detectionCanvas.getContext("2d");
        ctx.clearRect(0, 0, detectionCanvas.width || 0, detectionCanvas.height || 0);
    }

    function resizeDetectionOverlay() {
        if (!detectionCanvas || !video.videoWidth || !video.videoHeight) return;
        if (detectionCanvas.width !== video.videoWidth) detectionCanvas.width = video.videoWidth;
        if (detectionCanvas.height !== video.videoHeight) detectionCanvas.height = video.videoHeight;
    }

    function drawDetections(detections, validDetections) {
        if (!detectionCanvas || !video.videoWidth || !video.videoHeight) return;
        resizeDetectionOverlay();
        const ctx = detectionCanvas.getContext("2d");
        ctx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
        ctx.lineWidth = Math.max(3, Math.round(video.videoWidth / 220));
        ctx.font = `${Math.max(18, Math.round(video.videoWidth / 38))}px system-ui, sans-serif`;
        ctx.textBaseline = "top";

        detections.forEach((item, index) => {
            const box = item.box;
            const isValid = validDetections.includes(item);
            const color = isValid ? "#22c55e" : "#f59e0b";
            ctx.strokeStyle = color;
            ctx.fillStyle = color;
            ctx.strokeRect(box.x, box.y, box.width, box.height);
            const label = `${index + 1} ${(item.score * 100).toFixed(0)}%`;
            const labelY = Math.max(4, box.y - 28);
            ctx.fillText(label, box.x, labelY);
        });
    }

    function updateNetwork() {
        const online = navigator.onLine;
        setText("networkStatus", online ? "Online" : "Offline");
        setText("offlineBadge", online ? "Online" : "Offline");
        $("offlineBadge").classList.toggle("offline", !online);
        state.metrics.online_actual = online;
        if (!online) log("Modo offline activo. El laboratorio no registrara asistencias.");
    }

    async function registerServiceWorker() {
        if (!("serviceWorker" in navigator)) {
            setText("swStatus", "No soportado");
            state.metrics.service_worker = "no_soportado";
            return;
        }

        try {
            const registration = await navigator.serviceWorker.register(shell.dataset.swUrl, {
                scope: "/biometrico/laboratorio-offline/",
            });
            setText("swStatus", "Registrado");
            setText("swScope", registration.scope);
            setText("offlineReady", "Cache laboratorio activo");
            state.metrics.service_worker = "registrado";
            state.metrics.service_worker_scope = registration.scope;
            log("Service Worker experimental registrado para el laboratorio.");
        } catch (error) {
            setText("swStatus", "Error");
            state.metrics.service_worker = "error";
            state.metrics.service_worker_error = error.message;
            log(`No se pudo registrar el Service Worker: ${error.message}`);
        }
    }

    async function loadFaceModel() {
        if (!window.faceapi) {
            setText("modelStatus", "No disponible");
            log("face-api.js no esta disponible en la pagina.");
            return;
        }

        const start = nowMs();
        try {
            await Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri(shell.dataset.modelUrl),
                faceapi.nets.faceLandmark68Net.loadFromUri(shell.dataset.modelUrl),
                faceapi.nets.faceRecognitionNet.loadFromUri(shell.dataset.modelUrl),
            ]);
            const elapsed = nowMs() - start;
            state.modelLoaded = true;
            state.metrics.modelo_carga_ms = Number(elapsed.toFixed(2));
            state.metrics.backend_tfjs = faceapi.tf && faceapi.tf.getBackend ? faceapi.tf.getBackend() : "desconocido";
            setText("modelStatus", `Cargado (${state.metrics.backend_tfjs})`);
            log(`Modelo facial web cargado localmente en ${elapsed.toFixed(1)} ms.`);
        } catch (error) {
            state.modelLoaded = false;
            state.metrics.modelo_error = error.message;
            setText("modelStatus", "Error");
            log(`No se pudo cargar el modelo facial web: ${error.message}`);
        }
    }

    async function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setText("cameraStatus", "No soportada");
            log("Este navegador no permite acceso a camara.");
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "user",
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    frameRate: { ideal: 24, max: 30 },
                },
                audio: false,
            });
            video.srcObject = stream;
            await video.play();
            setText("cameraStatus", "Activa");
            resizeDetectionOverlay();
            log("Camara iniciada para prueba local.");
        } catch (error) {
            setText("cameraStatus", "Error");
            state.metrics.camera_error = error.message;
            log(`Error de camara: ${error.message}`);
        }
    }

    async function detectFaces({ silent = false, force = false } = {}) {
        if (!state.modelLoaded) {
            setText("faceStatus", "Modelo pendiente");
            if (!silent) log("Primero cargue el modelo facial web.");
            return { ok: false, reason: "modelo_pendiente", detections: [], validDetections: [] };
        }
        if (!video.videoWidth || !video.videoHeight) {
            setText("faceStatus", "Camara pendiente");
            if (!silent) log("Primero inicie la camara.");
            return { ok: false, reason: "camara_pendiente", detections: [], validDetections: [] };
        }

        const now = Date.now();
        if (!force && now - state.lastDetectionAt < MIN_DETECTION_INTERVAL_MS) {
            return { ok: false, reason: "frecuencia_limitada", detections: [], validDetections: [] };
        }
        state.lastDetectionAt = now;

        const options = new faceapi.TinyFaceDetectorOptions({
            inputSize: DETECTOR_INPUT_SIZE,
            scoreThreshold: DETECTOR_SCORE_THRESHOLD,
        });

        const start = nowMs();
        const detections = await faceapi.detectAllFaces(video, options);
        const elapsed = nowMs() - start;
        const minWidth = video.videoWidth * MIN_FACE_WIDTH_RATIO;
        const minHeight = video.videoHeight * MIN_FACE_HEIGHT_RATIO;
        const validDetections = detections.filter((item) => {
            return item.box.width >= minWidth && item.box.height >= minHeight;
        });

        drawDetections(detections, validDetections);
        setText("facesDetected", String(detections.length));
        setText("detectionTime", `${elapsed.toFixed(1)} ms`);

        state.metrics.ultima_deteccion = {
            input_size: DETECTOR_INPUT_SIZE,
            score_threshold: DETECTOR_SCORE_THRESHOLD,
            min_face_width_ratio: MIN_FACE_WIDTH_RATIO,
            min_face_height_ratio: MIN_FACE_HEIGHT_RATIO,
            video_width: video.videoWidth,
            video_height: video.videoHeight,
            rostros_detectados: detections.length,
            rostros_validos_por_tamano: validDetections.length,
            deteccion_ms: Number(elapsed.toFixed(2)),
            scores: detections.map((item) => Number(item.score.toFixed(6))),
            boxes: detections.map((item) => ({
                x: Number(item.box.x.toFixed(2)),
                y: Number(item.box.y.toFixed(2)),
                width: Number(item.box.width.toFixed(2)),
                height: Number(item.box.height.toFixed(2)),
            })),
        };

        if (!detections.length) {
            setText("faceStatus", "Sin rostro");
            setText("resultValue", "No detectado");
            if (!silent) log("Rostros detectados: 0. Acerque el rostro y mejore la iluminacion.");
            return { ok: false, reason: "sin_rostro", detections, validDetections };
        }

        if (!validDetections.length) {
            setText("faceStatus", "Rostro muy pequeno");
            setText("resultValue", "No valido");
            if (!silent) log(`Rostros detectados: ${detections.length}, pero ninguno supera el tamano minimo.`);
            return { ok: false, reason: "rostro_muy_pequeno", detections, validDetections };
        }

        if (validDetections.length > 1) {
            setText("faceStatus", "Varios rostros");
            setText("resultValue", "No valido");
            if (!silent) log(`Rostros detectados: ${detections.length}. Rostros validos: ${validDetections.length}. Debe haber una sola persona.`);
            return { ok: false, reason: "multiples_rostros", detections, validDetections };
        }

        setText("faceStatus", "✓ Rostro detectado");
        setText("resultValue", "Rostro detectado");
        if (!silent) log(`✓ Rostro detectado. Rostros detectados: ${detections.length}, validos: 1.`);
        return { ok: true, reason: "rostro_unico", detections, validDetections };
    }

    function captureFrame() {
        if (!video.videoWidth || !video.videoHeight) {
            log("No hay frame disponible para capturar.");
            return null;
        }

        const start = nowMs();
        const maxWidth = 640;
        const scale = Math.min(1, maxWidth / video.videoWidth);
        const width = Math.round(video.videoWidth * scale);
        const height = Math.round(video.videoHeight * scale);
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        canvas.width = width;
        canvas.height = height;
        ctx.drawImage(video, 0, 0, width, height);
        const imageData = ctx.getImageData(0, 0, width, height);
        const elapsed = nowMs() - start;

        setText("detectionTime", `${elapsed.toFixed(1)} ms captura`);
        setText("embeddingTime", "Sin motor web");
        setText("comparisonTime", "No ejecutada");
        setText("confidenceValue", "No disponible");
        setText("resultValue", "Inconcluso");

        state.metrics.ultima_captura = {
            width,
            height,
            captura_ms: Number(elapsed.toFixed(2)),
            bytes_rgba_aproximados: imageData.data.length,
        };
        state.metrics.compatibilidad_embeddings = "RESULTADO_INCONCLUSO";
        log("Frame capturado localmente. No se envio imagen al servidor.");
        return imageData;
    }

    function euclideanDistance(a, b) {
        if (!a || !b || a.length !== b.length) return Infinity;
        let sum = 0;
        for (let i = 0; i < a.length; i += 1) {
            const diff = Number(a[i]) - Number(b[i]);
            sum += diff * diff;
        }
        return Math.sqrt(sum);
    }

    function cosineSimilarity(a, b) {
        if (!a || !b || a.length !== b.length) return null;
        let dot = 0;
        let na = 0;
        let nb = 0;
        for (let i = 0; i < a.length; i += 1) {
            const av = Number(a[i]);
            const bv = Number(b[i]);
            dot += av * bv;
            na += av * av;
            nb += bv * bv;
        }
        if (!na || !nb) return null;
        return dot / (Math.sqrt(na) * Math.sqrt(nb));
    }

    function norm(a) {
        if (!a) return null;
        let sum = 0;
        for (let i = 0; i < a.length; i += 1) sum += Number(a[i]) * Number(a[i]);
        return Math.sqrt(sum);
    }

    async function generateWebEmbedding() {
        const detection = await detectFaces({ force: true });
        if (!detection.ok) {
            setText("embeddingTime", "No ejecutado");
            setText("confidenceValue", "No disponible");
            log("No se detecto un rostro unico para generar embedding.");
            return null;
        }

        const options = new faceapi.TinyFaceDetectorOptions({
            inputSize: DETECTOR_INPUT_SIZE,
            scoreThreshold: DETECTOR_SCORE_THRESHOLD,
        });

        const start = nowMs();
        const result = await faceapi
            .detectSingleFace(video, options)
            .withFaceLandmarks()
            .withFaceDescriptor();
        const elapsed = nowMs() - start;

        if (!result || !result.descriptor) {
            setText("resultValue", "Sin rostro");
            log("La deteccion previa fue valida, pero no se pudo generar embedding.");
            return null;
        }

        const descriptor = Array.from(result.descriptor);
        const detectionMs = elapsed * 0.35;
        const embeddingMs = elapsed * 0.65;
        state.currentEmbedding = descriptor;
        state.currentEmbeddingMeta = {
            dimension: descriptor.length,
            tipo_numerico: "float32",
            generado_en: new Date().toISOString(),
        };
        setText("embeddingDimension", String(descriptor.length));
        setText("detectionTime", `${detectionMs.toFixed(1)} ms aprox.`);
        setText("embeddingTime", `${embeddingMs.toFixed(1)} ms aprox.`);
        setText("comparisonTime", "Pendiente");
        setText("confidenceValue", "Pendiente");
        setText("resultValue", "Embedding generado");

        state.metrics.ultimo_embedding_web = {
            dimension: descriptor.length,
            tipo_numerico: "float32",
            tiempo_total_ms: Number(elapsed.toFixed(2)),
            deteccion_alineacion_ms_aprox: Number(detectionMs.toFixed(2)),
            embedding_ms_aprox: Number(embeddingMs.toFixed(2)),
            score_deteccion: Number(result.detection.score.toFixed(6)),
            norma: Number(norm(descriptor).toFixed(6)),
        };

        log(`Embedding web generado localmente: dimension ${descriptor.length}, score ${result.detection.score.toFixed(3)}.`);
        return descriptor;
    }

    function compareWithDescriptorSlot(slot) {
        const dlibItem = slot === "A" ? state.descriptorA : state.descriptorB;
        if (!state.currentEmbedding) {
            setText("resultValue", "Genere embedding");
            log("Primero genere un embedding desde la camara.");
            return null;
        }
        if (!dlibItem || !dlibItem.descriptor) {
            setText("resultValue", `Descriptor ${slot} pendiente`);
            log(`Primero cargue una muestra con descriptor ${slot}.`);
            return null;
        }

        const start = nowMs();
        const distance = euclideanDistance(state.currentEmbedding, dlibItem.descriptor);
        const cosine = cosineSimilarity(state.currentEmbedding, dlibItem.descriptor);
        const elapsed = nowMs() - start;
        const result = {
            descriptor_slot: slot,
            descriptor_token_anonimo: dlibItem.token,
            dimension_web: state.currentEmbedding.length,
            dimension_dlib: dlibItem.dimension,
            distancia_euclidiana: Number(distance.toFixed(6)),
            similitud_coseno: cosine === null ? null : Number(cosine.toFixed(6)),
            comparacion_ms: Number(elapsed.toFixed(2)),
            embedding_generado_en: state.currentEmbeddingMeta ? state.currentEmbeddingMeta.generado_en : null,
        };

        setText("embeddingDimension", `${result.dimension_web} / ${result.dimension_dlib}`);
        setText("comparisonTime", `${elapsed.toFixed(2)} ms`);
        setText("confidenceValue", `Distancia ${result.distancia_euclidiana} | Coseno ${result.similitud_coseno}`);
        setText("resultValue", `Comparado contra descriptor ${slot}`);

        if (!state.metrics.comparaciones_embedding_dlib) {
            state.metrics.comparaciones_embedding_dlib = [];
        }
        state.metrics.comparaciones_embedding_dlib.push(result);
        state.metrics.ultima_comparacion_dlib = result;

        log(`Comparacion local contra descriptor ${slot}: distancia ${result.distancia_euclidiana}, coseno ${result.similitud_coseno}.`);
        return result;
    }

    async function compareCurrentCapture() {
        await detectFaces();
    }

    async function saveSample(slot) {
        const descriptor = await generateWebEmbedding();
        if (!descriptor) return;
        state[slot] = descriptor;
        log(`${slot === "sampleA" ? "Captura A" : "Captura B"} guardada en memoria temporal del navegador.`);

        if (state.sampleA && state.sampleB) {
            const d = euclideanDistance(state.sampleA, state.sampleB);
            const c = cosineSimilarity(state.sampleA, state.sampleB);
            state.metrics.comparacion_web_a_b = {
                distancia_euclidiana: Number(d.toFixed(6)),
                similitud_coseno: c === null ? null : Number(c.toFixed(6)),
                esperado: "misma_persona_si_ambas_capturas_son_del_mismo_funcionario",
            };
            log(`Comparacion web A/B en memoria: distancia ${d.toFixed(6)}.`);
        }
    }

    async function loadDescriptorSample() {
        const start = nowMs();
        try {
            const response = await fetch(`${shell.dataset.descriptoresUrl}?limite=10`, {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" },
            });
            const payload = await response.json();
            if (!payload.ok) throw new Error(payload.error || "No fue posible cargar la muestra.");

            state.descriptors = payload.descriptores || [];
            state.descriptorA = state.descriptors[0] || null;
            state.descriptorB = state.descriptors[1] || null;
            const elapsed = nowMs() - start;
            setText("loadedDescriptors", String(state.descriptors.length));
            setText("descriptorAStatus", state.descriptorA ? `A listo (${state.descriptorA.dimension})` : "No disponible");
            setText("descriptorBStatus", state.descriptorB ? `B listo (${state.descriptorB.dimension})` : "No disponible");
            state.metrics.descriptores_muestra = {
                cantidad: state.descriptors.length,
                carga_ms: Number(elapsed.toFixed(2)),
                dimension: state.descriptors[0] ? state.descriptors[0].dimension : 0,
                tipo_numerico_origen: state.descriptors[0] ? state.descriptors[0].tipo_numerico_origen : null,
                tipo_numerico_transporte: state.descriptors[0] ? state.descriptors[0].tipo_numerico_transporte : null,
                bytes_por_descriptor: state.descriptors[0] ? state.descriptors[0].bytes : 0,
                transporte: "json_temporal_limitado_anonimo",
            };
            log(`Muestra limitada cargada: ${state.descriptors.length} descriptor(es). Descriptor A/B listos si hay al menos dos registros.`);
        } catch (error) {
            state.metrics.descriptores_error = error.message;
            log(`Error al cargar descriptores: ${error.message}`);
        }
    }

    function openDb() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open("clockin_biometrico_lab_fase0", 1);
            request.onupgradeneeded = function () {
                const db = request.result;
                if (!db.objectStoreNames.contains("descriptores_ficticios")) {
                    db.createObjectStore("descriptores_ficticios", { keyPath: "token" });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    function txDone(tx) {
        return new Promise((resolve, reject) => {
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
    }

    function fakeDescriptor(index) {
        const descriptor = new Array(128);
        for (let i = 0; i < descriptor.length; i += 1) {
            descriptor[i] = Math.sin(index * 0.017 + i * 0.031);
        }
        return {
            token: `fake-${index}`,
            dimension: 128,
            tipo_numerico: "float64_simulado_js",
            descriptor,
        };
    }

    function distance(a, b) {
        let sum = 0;
        for (let i = 0; i < a.length; i += 1) {
            const diff = a[i] - b[i];
            sum += diff * diff;
        }
        return Math.sqrt(sum);
    }

    async function runIndexedDbTest(size) {
        const db = await openDb();
        const writeStart = nowMs();
        const txWrite = db.transaction("descriptores_ficticios", "readwrite");
        const storeWrite = txWrite.objectStore("descriptores_ficticios");
        storeWrite.clear();
        for (let i = 0; i < size; i += 1) {
            storeWrite.put(fakeDescriptor(i));
        }
        await txDone(txWrite);
        const writeMs = nowMs() - writeStart;

        const readStart = nowMs();
        const txRead = db.transaction("descriptores_ficticios", "readonly");
        const storeRead = txRead.objectStore("descriptores_ficticios");
        const records = await new Promise((resolve, reject) => {
            const request = storeRead.getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
        await txDone(txRead);
        const readMs = nowMs() - readStart;

        const compareStart = nowMs();
        const probe = fakeDescriptor(size + 1).descriptor;
        let best = Infinity;
        for (const record of records) {
            const current = distance(probe, record.descriptor);
            if (current < best) best = current;
        }
        const compareMs = nowMs() - compareStart;

        const estimatedBytes = size * 128 * 8;
        const result = {
            cantidad: size,
            escritura_ms: Number(writeMs.toFixed(2)),
            lectura_ms: Number(readMs.toFixed(2)),
            comparacion_lineal_ms: Number(compareMs.toFixed(2)),
            tamano_estimado_bytes: estimatedBytes,
            mejor_distancia_ficticia: Number(best.toFixed(6)),
        };

        state.metrics.indexeddb.push(result);
        indexedDbOutput.textContent = JSON.stringify(result, null, 2);
        setText("comparisonTime", `${result.comparacion_lineal_ms} ms ficticio`);
        log(`IndexedDB probado con ${size} descriptores ficticios.`);
    }

    async function clearIndexedDb() {
        const db = await openDb();
        const tx = db.transaction("descriptores_ficticios", "readwrite");
        tx.objectStore("descriptores_ficticios").clear();
        await txDone(tx);
        indexedDbOutput.textContent = "Datos ficticios eliminados.";
        log("Base IndexedDB del laboratorio limpiada.");
    }

    function exportMetrics() {
        state.metrics.exportado_en = new Date().toISOString();
        const blob = new Blob([JSON.stringify(state.metrics, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "biometrico_offline_fase0_metricas_locales.json";
        a.click();
        URL.revokeObjectURL(url);
        log("Metricas exportadas localmente desde el navegador.");
    }

    function bindEvents() {
        window.addEventListener("online", updateNetwork);
        window.addEventListener("offline", updateNetwork);
        $("btnModel").addEventListener("click", loadFaceModel);
        $("btnCamera").addEventListener("click", startCamera);
        $("btnCapture").addEventListener("click", compareCurrentCapture);
        $("btnGenerateEmbedding").addEventListener("click", generateWebEmbedding);
        $("btnSampleA").addEventListener("click", async () => {
            const descriptor = await generateWebEmbedding();
            if (descriptor) {
                state.sampleA = descriptor;
                log("Embedding A guardado temporalmente en memoria del navegador.");
            }
        });
        $("btnSampleB").addEventListener("click", async () => {
            const descriptor = await generateWebEmbedding();
            if (descriptor) {
                state.sampleB = descriptor;
                log("Embedding B guardado temporalmente en memoria del navegador.");
            }
        });
        $("btnDescriptors").addEventListener("click", loadDescriptorSample);
        $("btnCompareDescriptorA").addEventListener("click", () => compareWithDescriptorSlot("A"));
        $("btnCompareDescriptorB").addEventListener("click", () => compareWithDescriptorSlot("B"));
        $("btnIndexedDb").addEventListener("click", () => runIndexedDbTest(100));
        $("btnExport").addEventListener("click", exportMetrics);
        $("btnClearDb").addEventListener("click", clearIndexedDb);
        document.querySelectorAll("[data-idb-size]").forEach((button) => {
            button.addEventListener("click", () => runIndexedDbTest(Number(button.dataset.idbSize)));
        });
    }

    updateNetwork();
    bindEvents();
    registerServiceWorker();
    setText("modelStatus", "Pendiente de carga");
    log("Motor facial web local disponible. Cargue el modelo para iniciar la prueba critica.");
}());
