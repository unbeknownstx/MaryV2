const CACHE='maryv2-mobile-shell-v13-2-unified-v13-7-product-polish';
const SHELL=[
  '/',
  '/index.html',
  '/style.css',
  '/experience.css',
  '/polish-13-7.css',
  '/app.js',
  '/experience.js',
  '/manifest.webmanifest',
  '/assets/mary-icon.png',
  '/assets/mary-icon-192.png',
  '/assets/mary-icon-180.png',
  '/assets/mary-reference.jpeg',
  '/assets/mary-stream-room-reference.png',
  '/assets/mary-neon-night-manga.png',
  '/assets/cyber-grid.svg',
  '/assets/mary-sigil.svg'
];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>cache.addAll(SHELL))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

async function networkFirst(request){
  try{
    const response=await fetch(request);
    if(response.ok){
      const cache=await caches.open(CACHE);
      cache.put(request,response.clone());
    }
    return response;
  }catch(error){
    const cached=await caches.match(request);
    if(cached)return cached;
    if(request.mode==='navigate')return caches.match('/index.html');
    throw error;
  }
}

self.addEventListener('fetch',event=>{
  const request=event.request;
  const url=new URL(request.url);
  if(url.origin!==location.origin||url.pathname.startsWith('/api/')||request.method!=='GET')return;

  const suffix=url.pathname.split('.').pop()?.toLowerCase();
  const appCode=request.mode==='navigate'||['html','js','css','webmanifest'].includes(suffix);
  if(appCode){
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(
    caches.match(request).then(cached=>cached||fetch(request).then(response=>{
      if(response.ok){
        const copy=response.clone();
        caches.open(CACHE).then(cache=>cache.put(request,copy));
      }
      return response;
    }))
  );
});
