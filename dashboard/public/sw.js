// Service worker cache strategy:
//   /_next/static + /icons : cache-first (content-hashed, immutable)
//   everything else (HTML, /api) : network-first, cache fallback for offline.
// Network-first pages mean deploys are visible immediately; the runtime
// cache still serves the last-seen copy when offline.
// Bump CACHE_NAME on strategy changes so old caches are purged on activate.
const CACHE_NAME = 'lifegraph-v3';

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

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  const title = data.title || "Life Graph";
  const body = data.body || "";
  const url = data.url || "/m";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/m";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w) { w.navigate(url); return w.focus(); }
      }
      return self.clients.openWindow(url);
    })
  );
});
