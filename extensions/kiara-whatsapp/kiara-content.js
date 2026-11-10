(() => {
  const origin = window.location.origin
  window.addEventListener("message", event => {
    if (event.source !== window || event.origin !== origin) return
    const request = event.data
    if (request?.source === "kiara-app" && request.type === "whatsapp-prepare"
        && typeof request.requestId === "string") {
      chrome.runtime.sendMessage({ type: "kiara-whatsapp-prepare" }).then(response => {
        window.postMessage({
          source: "kiara-whatsapp-extension",
          type: "whatsapp-ready",
          requestId: request.requestId,
          error: response?.error || null,
        }, origin)
      }).catch(() => {
        window.postMessage({
          source: "kiara-whatsapp-extension",
          type: "whatsapp-ready",
          requestId: request.requestId,
          error: "A extensão Kiara não conseguiu preparar o WhatsApp Web.",
        }, origin)
      })
      return
    }
    if (request?.source !== "kiara-app" || request.type !== "whatsapp-analysis") return
    if (typeof request.jobId !== "string" || !/^[0-9a-f-]{36}$/i.test(request.jobId)) return
    chrome.runtime.sendMessage({
      type: "kiara-analysis-request",
      jobId: request.jobId,
      limit: Math.max(1, Math.min(30, Number(request.limit) || 30)),
    }).then(response => {
      window.postMessage({
        source: "kiara-whatsapp-extension",
        type: "analysis-status",
        jobId: request.jobId,
        error: response?.error || null,
      }, origin)
    }).catch(() => {
      window.postMessage({
        source: "kiara-whatsapp-extension",
        type: "analysis-status",
        jobId: request.jobId,
        error: "A extensão Kiara não respondeu. Confira se ela está instalada e ativa no Chrome.",
      }, origin)
    })
  })
})()
