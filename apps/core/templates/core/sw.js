const CACHE_PREFIX = "sharecar-pwa-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;
const OFFLINE_URL = "{{ offline_url|escapejs }}";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.add(new Request(OFFLINE_URL, {
        credentials: "omit",
        cache: "reload",
      })))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names
        .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
        .map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || request.mode !== "navigate" ||
      new URL(request.url).origin !== self.location.origin) {
    return;
  }

  // Não armazenar HTML, arquivos de usuários, APIs, CDNs ou operações POST.
  // Evita também reutilizar páginas autenticadas do cache HTTP do navegador.
  event.respondWith(fetch(request, { cache: "no-store" }).catch(async () => {
    const cache = await caches.open(CACHE_NAME);
    return await cache.match(OFFLINE_URL) || new Response(
      "Sem conexão com o ShareCar. Verifique se o servidor está em execução.",
      { status: 503, headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-store",
      } }
    );
  }));
});
