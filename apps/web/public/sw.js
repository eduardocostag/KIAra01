/* Kiara app (PWA) service worker.
 * Deliberately stores nothing: every page and API call goes to the network as usual, so no account data is ever
 * kept on the phone and updates arrive on the next open. Its only job is a friendly screen when there is no
 * connection, instead of the browser's error page. */
const OFFLINE = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Kiara · sem conexão</title>
<style>html,body{height:100%;margin:0}body{display:grid;place-items:center;background:#0d0b18;color:#ece9ff;font:16px/1.5 system-ui,-apple-system,sans-serif;text-align:center;padding:24px}
.orb{width:84px;height:84px;margin:0 auto 22px;border-radius:50%;background:radial-gradient(circle at 40% 30%,#e4ccff,#a868f5 28%,#6a26c4 62%,#2a1158);box-shadow:0 0 50px -6px #7c4dff}
h1{font-size:20px;margin:0 0 8px}p{margin:0 0 22px;color:#a9a3c7}button{border:0;border-radius:999px;padding:12px 22px;background:#7c4dff;color:#fff;font:600 15px system-ui,sans-serif}</style></head>
<body><main><div class="orb"></div><h1>Você está sem internet</h1><p>A Kiara volta assim que a conexão voltar.</p><button onclick="location.reload()">Tentar de novo</button></main></body></html>`

self.addEventListener("install", () => self.skipWaiting())
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()))

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return
  event.respondWith(fetch(event.request).catch(() => new Response(OFFLINE, { headers: { "Content-Type": "text/html; charset=utf-8" } })))
})
