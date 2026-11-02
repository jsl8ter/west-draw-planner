/* West Draw Planner service worker: app shell offline, data refreshed in the background,
   recently viewed map tiles kept for offline use. */
const V = "wdp-v12";
const SHELL = ["./", "index.html", "odds.js", "plan.js", "manifest.webmanifest", "icons/icon-192.png", "icons/apple-touch-icon.png",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"];
const TILE_MAX = 1500;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(V + "-shell").then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => null)))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => !k.startsWith(V)).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

async function networkFirst(req, cacheName) {
  const c = await caches.open(cacheName);
  try { const r = await fetch(req); if (r && r.ok) c.put(req, r.clone()); return r; }
  catch (e) { const hit = await c.match(req, { ignoreSearch: true }); if (hit) return hit; throw e; }
}
async function staleWhileRevalidate(req, cacheName) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req, { ignoreSearch: true });
  const net = fetch(req).then(r => { if (r && (r.ok || r.type === "opaque")) c.put(req, r.clone()); return r; }).catch(() => null);
  return hit || (await net) || Response.error();
}
async function tile(req) {
  const c = await caches.open(V + "-tiles");
  const hit = await c.match(req);
  if (hit) return hit;
  try {
    const r = await fetch(req);
    if (r && (r.ok || r.type === "opaque")) {
      c.put(req, r.clone());
      c.keys().then(ks => { if (ks.length > TILE_MAX) ks.slice(0, ks.length - TILE_MAX).forEach(k => c.delete(k)); });
    }
    return r;
  } catch (e) { return Response.error(); }
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const u = new URL(req.url);
  if (/\/tile\/\d+\/\d+\/\d+/.test(u.pathname)) { e.respondWith(tile(req)); return; }
  if (u.origin === location.origin) {
    if (req.mode === "navigate" || u.pathname.endsWith(".html") || u.pathname.endsWith("odds.js") || u.pathname.endsWith("plan.js")) { e.respondWith(networkFirst(req, V + "-shell")); return; }
    if (u.pathname.includes("/data/")) { e.respondWith(staleWhileRevalidate(req, V + "-data")); return; }
    e.respondWith(staleWhileRevalidate(req, V + "-shell")); return;
  }
  if (/cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com/.test(u.hostname)) { e.respondWith(staleWhileRevalidate(req, V + "-shell")); }
});
