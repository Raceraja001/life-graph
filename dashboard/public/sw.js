// Service worker cache strategy:
//   /_next/static + /icons : cache-first (content-hashed, immutable)
//   everything else (HTML, /api) : network-first, cache fallback for offline.
// Network-first pages mean deploys are visible immediately; the runtime
// cache still serves the last-seen copy when offline.
// Bump CACHE_NAME on strategy changes so old caches are purged on activate.
const CACHE_NAME = 'lifegraph-v2';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

function cacheThenNetwork(request) {
  return caches.match(request).then((cached) =>
    cached ||
    fetch(request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE_NAME).then((c) => c.put(request, copy));
      return res;
    })
  );
}

function networkThenCache(request) {
  return fetch(request)
    .then((res) => {
      const copy = res.clone();
      caches.open(CACHE_NAME).then((c) => c.put(request, copy));
      return res;
    })
    .catch(() => caches.match(request));
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.pathname.startsWith('/_next/static/') || url.pathname.startsWith('/icons/')) {
    event.respondWith(cacheThenNetwork(request));
  } else {
    event.respondWith(networkThenCache(request));
  }
});
