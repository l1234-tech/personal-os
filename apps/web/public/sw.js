const CACHE_NAME = 'personal-os-shell-v1'
const SHELL = ['/', '/manifest.webmanifest']
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)))
  self.skipWaiting()
})
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))))
  self.clients.claim()
})
self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  event.respondWith(fetch(request).then((response) => {
    if (response.ok && request.mode === 'navigate') {
      const copy = response.clone()
      void caches.open(CACHE_NAME).then((cache) => cache.put('/', copy))
    }
    return response
  }).catch(async () => (await caches.match(request)) || caches.match('/')))
})
