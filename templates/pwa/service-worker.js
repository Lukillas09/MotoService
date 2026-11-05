{% autoescape off %}// Generado por apps.core.views.service_worker. El nombre de caché cambia sólo
// cuando cambia la versión o algún recurso precargado.
const CACHE_NAME = "{{ nombre_cache }}";
const OFFLINE_URL = "{{ offline_url }}";
const STATIC_PREFIX = "{{ prefijo_estaticos }}";
const STATIC_ASSETS = {{ recursos_json }};

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll([...STATIC_ASSETS, OFFLINE_URL]))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Navegaciones: siempre desde la red y nunca se guardan, porque el HTML puede
  // ser privado. Sin conexión se muestra la página offline precargada.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(OFFLINE_URL).then((offline) => offline || Response.error())
      )
    );
    return;
  }

  // HTMX y cualquier otra respuesta dinámica quedan fuera del service worker.
  if (!url.pathname.startsWith(STATIC_PREFIX)) return;

  // Estáticos: cache-first.
  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});
{% endautoescape %}
