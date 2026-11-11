const CACHE_NAME = "{{ cache_name }}";
const OFFLINE_URL = "{{ offline_url }}";
const STATIC_PATH = "{{ static_url }}";
const PRECACHE_ASSETS = {{ assets_json|safe }};

const CDN_HOSTS = new Set([
  "cdn.jsdelivr.net",
  "fonts.googleapis.com",
  "fonts.gstatic.com",
]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll([...PRECACHE_ASSETS, OFFLINE_URL]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((chaves) =>
        Promise.all(
          chaves
            .filter((chave) => chave !== CACHE_NAME)
            .map((chave) => caches.delete(chave))
        )
      )
      .then(() => self.clients.claim())
  );
});

const respostaOffline = () =>
  caches.match(OFFLINE_URL).then((resposta) => {
    if (resposta) {
      return resposta;
    }
    return new Response(
      "<!DOCTYPE html><html lang=\"pt-BR\"><meta charset=\"utf-8\"><title>Sem conexão</title><body><h1>Sem conexão</h1><p>Verifique sua internet e tente novamente.</p></body></html>",
      { headers: { "Content-Type": "text/html; charset=utf-8" } }
    );
  });

const cachearResposta = (request, response) => {
  if (!response || (!response.ok && response.type !== "opaque")) {
    return response;
  }
  const copia = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(request, copia));
  return response;
};

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // Navegação: rede primeiro e tela offline como fallback.
  // Páginas autenticadas não são armazenadas no cache.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => respostaOffline())
    );
    return;
  }

  // Arquivos estáticos do próprio site: cache primeiro, com atualização em segundo plano.
  if (url.origin === self.location.origin && url.pathname.startsWith(STATIC_PATH)) {
    event.respondWith(
      caches.match(request).then((cacheado) => {
        if (cacheado) {
          fetch(request)
            .then((response) => cachearResposta(request, response))
            .catch(() => {});
          return cacheado;
        }
        return fetch(request).then((response) =>
          cachearResposta(request, response)
        );
      })
    );
    return;
  }

  // Fontes e bibliotecas de CDN já visitadas ficam disponíveis offline.
  if (CDN_HOSTS.has(url.host)) {
    event.respondWith(
      caches.match(request).then((cacheado) => {
        if (cacheado) {
          return cacheado;
        }
        return fetch(request).then((response) =>
          cachearResposta(request, response)
        );
      })
    );
  }
});
