/* Revela: cache do app e dos modelos para funcionar sem internet depois da primeira abertura. */
const VERSION = "revela-v4";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];
// bibliotecas e modelos, para o app funcionar sem internet desde a primeira instalação
const HEAVY = ["vendor/mediapipe/vision_bundle.mjs", "vendor/mediapipe/wasm/vision_wasm_internal.js", "vendor/mediapipe/wasm/vision_wasm_internal.wasm", "vendor/models/selfie_multiclass_256x256.tflite", "vendor/models/face_landmarker.task"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL).then(() => c.addAll(HEAVY).catch(() => {}))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    // arquivos do app: rede primeiro, cache se estiver sem internet
    e.respondWith(fetch(req).then(res => { const cp = res.clone(); caches.open(VERSION).then(c => c.put(req, cp)); return res; }).catch(() => caches.match(req).then(h => h || caches.match("index.html"))));
    return;
  }
  // modelos, bibliotecas e fontes: cache primeiro
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res.ok || res.type === "opaque") { const cp = res.clone(); caches.open(VERSION).then(c => c.put(req, cp)); }
    return res;
  })));
});
