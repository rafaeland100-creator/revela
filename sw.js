/* Revela: cache do app e dos modelos para funcionar sem internet depois da primeira abertura. */
const VERSION = "revela-v22";
// a rede própria do app (IA Revela) é pequena e entra junto com a casca
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "vendor/models/revela_tom.bin"];
// bibliotecas e modelos, para o app funcionar sem internet desde a primeira instalação
const HEAVY = ["vendor/mediapipe/vision_bundle.mjs", "vendor/mediapipe/wasm/vision_wasm_internal.js", "vendor/mediapipe/wasm/vision_wasm_internal.wasm", "vendor/models/selfie_multiclass_256x256.tflite", "vendor/models/face_landmarker.task", "vendor/ort/ort.wasm.min.mjs", "vendor/ort/ort-wasm-simd-threaded.mjs", "vendor/ort/ort-wasm-simd-threaded.wasm", "vendor/models/realesr-general-x4v3.onnx", "vendor/models/depth_anything_v2_small_int8.onnx", "vendor/models/segformer_b1_ade_q.onnx", "vendor/models/migan_pipeline_v2.onnx"];

self.addEventListener("install", e => {
  // no app Android os modelos já vêm dentro do APK; só o site precisa guardá-los
  const heavy = self.location.hostname === "localhost" && self.location.port === "" ? [] : HEAVY;
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL).then(() => c.addAll(heavy).catch(() => {}))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

// cabeçalhos que liberam a IA a usar vários núcleos do processador (isolamento de origem)
const withCOI = res => {
  if (!res || res.status === 0 || res.type === "opaque" || res.type === "opaqueredirect") return res;
  const h = new Headers(res.headers); h.set("Cross-Origin-Opener-Policy", "same-origin"); h.set("Cross-Origin-Embedder-Policy", "credentialless"); h.set("Cross-Origin-Resource-Policy", "same-origin");
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
};
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const nativeApp = self.location.hostname === "localhost" && self.location.port === "";
  if (nativeApp) { if (req.mode === "navigate") e.respondWith(fetch(req).then(withCOI)); return; }
  if (url.origin === self.location.origin) {
    // arquivos do app: rede primeiro, cache se estiver sem internet
    e.respondWith(fetch(req).then(res => { const cp = res.clone(); caches.open(VERSION).then(c => c.put(req, cp)); return withCOI(res); }).catch(() => caches.match(req).then(h => withCOI(h || null) || caches.match("index.html").then(withCOI))));
    return;
  }
  // modelos, bibliotecas e fontes: cache primeiro
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res.ok || res.type === "opaque") { const cp = res.clone(); caches.open(VERSION).then(c => c.put(req, cp)); }
    return res;
  })));
});
