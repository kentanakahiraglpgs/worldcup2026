// W杯2026 service worker — offline cache
const CACHE = "wc2026-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./results.json",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png",
  "./favicon.png"
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// network-first for the page, cache-first for static assets
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  // results.json は常に最新を優先（ネットワーク優先・失敗時のみキャッシュ）
  if (req.url.includes("results.json")) {
    e.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put("./results.json", copy));
        return res;
      }).catch(() => caches.match("./results.json"))
    );
    return;
  }
  const isDoc = req.mode === "navigate" || req.destination === "document";
  if (isDoc) {
    e.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put("./index.html", copy));
        return res;
      }).catch(() => caches.match("./index.html"))
    );
  } else {
    e.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
        return res;
      }).catch(() => hit))
    );
  }
});
