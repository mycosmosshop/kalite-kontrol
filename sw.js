// Sanifoam Kalite Kontrol — Service Worker (PWA)
// Strateji: GET istekleri network-first + cache fallback (çevrimdışı app kabuğu).
// Supabase API/auth ve POST/PUT/PATCH/DELETE asla cache'lenmez (veri her zaman canlı).
const CACHE = 'kk-cache-v71';

self.addEventListener('install', (e) => { self.skipWaiting(); });

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (e) => { if (e.data === 'skipWaiting') self.skipWaiting(); });

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                 // yazma isteklerine dokunma
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;
  if (url.hostname.endsWith('supabase.co')) return;  // veri/auth → her zaman ağ
  if (url.hostname === '127.0.0.1' || url.hostname === 'localhost') return;  // yerel ajan → SW dokunmasın (PNA)
  e.respondWith((async () => {
    try {
      const fresh = await fetch(req);
      if (fresh && fresh.status === 200 && (fresh.type === 'basic' || fresh.type === 'cors')) {
        const c = await caches.open(CACHE);
        c.put(req, fresh.clone());
      }
      return fresh;
    } catch (err) {
      const cached = await caches.match(req);
      if (cached) return cached;
      // navigasyon isteği çevrimdışı → ana sayfayı dene
      if (req.mode === 'navigate') {
        const home = await caches.match('kalite_kontrol.html');
        if (home) return home;
      }
      throw err;
    }
  })());
});
