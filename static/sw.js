self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('andina-pro-store').then((cache) => cache.addAll([
      '/',
      '/config',
      '/static/css/style.css',
      '/static/js/app.js',
      '/static/manifest.json'
    ])),
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((response) => response || fetch(e.request)),
  );
});
