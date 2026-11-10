const allowedKiaraOrigins = new Set(["https://kiaralead.vercel.app"])
const bridgeBase = "http://127.0.0.1:17843/v1"
let analysisInProgress = false
let commandInProgress = false
let activeCommand = null
let connectedTabId = null

async function bridgePost(path, body = {}) {
  const response = await fetch(`${bridgeBase}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error("O executor local da Kiara não está disponível.")
  return response.json()
}

async function connectWhatsAppTab() {
  const tabs = await chrome.tabs.query({ url: "https://web.whatsapp.com/*" })
  if (tabs.length) {
    const tab = tabs.find(candidate => candidate.active) || tabs[0]
    if (tab.id === undefined) throw new Error("Não consegui acessar a guia do WhatsApp Web.")
    connectedTabId = tab.id
    await chrome.tabs.update(tab.id, { active: true })
    if (tab.windowId !== undefined) await chrome.windows.update(tab.windowId, { focused: true })
    return tab.id
  }
  const tab = await chrome.tabs.create({ url: "https://web.whatsapp.com/", active: true })
  if (tab.id === undefined) throw new Error("Não consegui abrir o WhatsApp Web no Chrome.")
  connectedTabId = tab.id
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener)
      reject(new Error("O WhatsApp Web demorou para abrir. Tente novamente."))
    }, 30000)
    function listener(tabId, changeInfo) {
      if (tabId !== tab.id || changeInfo.status !== "complete") return
      clearTimeout(timeout)
      chrome.tabs.onUpdated.removeListener(listener)
      resolve()
    }
    chrome.tabs.onUpdated.addListener(listener)
  })
  return tab.id
}

async function scanTab(tabId, limit) {
  let lastError
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      const response = await chrome.tabs.sendMessage(tabId, { type: "kiara-scan-whatsapp", limit })
      if (!response?.ok) throw new Error(response?.error || "Não foi possível ler o WhatsApp Web.")
      return response.result
    } catch (error) {
      lastError = error
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }
  throw new Error(lastError?.message?.includes("Receiving end")
    ? "Atualize a guia do WhatsApp Web uma vez para ativar a extensão Kiara."
    : "A extensão não conseguiu acessar a guia do WhatsApp Web.")
}

async function prepareWhatsApp() {
  const tabId = await connectWhatsAppTab()
  let lastError
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      const response = await chrome.tabs.sendMessage(tabId, { type: "kiara-whatsapp-status" })
      if (!response?.ready) {
        throw new Error("WhatsApp Web não conectado. Entre na sua conta nessa guia e tente novamente.")
      }
      return
    } catch (error) {
      if (error instanceof Error && error.message.startsWith("WhatsApp Web não conectado.")) throw error
      lastError = error
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }
  throw new Error(lastError?.message?.includes("Receiving end")
    ? "Atualize a guia do WhatsApp Web uma vez para ativar a extensão Kiara."
    : "Não consegui confirmar a conexão do WhatsApp Web no Chrome.")
}

async function requestAnalysis(request) {
  const tabId = await connectWhatsAppTab()
  const result = await scanTab(tabId, request.limit)
  await bridgePost("scan", { job_id: request.jobId, ...result })
}

chrome.runtime.onMessage.addListener((request, sender, respond) => {
  if (request?.type === "kiara-whatsapp-heartbeat") {
    if (sender.url?.startsWith("https://web.whatsapp.com/")) {
      if (connectedTabId === null && sender.tab?.id !== undefined) connectedTabId = sender.tab.id
      if (sender.tab?.id === connectedTabId) {
        bridgePost("heartbeat", { ready: Boolean(request.ready) }).then(() => processNextCommand()).catch(() => {})
      }
    }
    return false
  }
  if (request?.type === "kiara-whatsapp-authorize") {
    if (!activeCommand || sender.tab?.id !== connectedTabId
        || request.id !== activeCommand.id || request.phone !== activeCommand.phone) {
      respond({ allowed: false })
      return false
    }
    bridgePost("commands/authorize", { id: request.id, phone: request.phone }).then(respond,
      () => respond({ allowed: false }))
    return true
  }
  if (request?.type === "kiara-whatsapp-prepare") {
    if (!sender.url || !allowedKiaraOrigins.has(new URL(sender.url).origin)) {
      respond({ error: "Solicitação não autorizada." })
      return false
    }
    prepareWhatsApp().then(
      () => respond({ error: null }),
      error => respond({ error: error instanceof Error ? error.message : "Falha ao conectar o WhatsApp Web." })
    )
    return true
  }
  if (request?.type !== "kiara-analysis-request") return false
  if (!sender.url || !allowedKiaraOrigins.has(new URL(sender.url).origin)
      || typeof request.jobId !== "string" || !/^[0-9a-f-]{36}$/i.test(request.jobId)) {
    respond({ error: "Solicitação de análise não autorizada." })
    return false
  }
  if (analysisInProgress || commandInProgress) {
    respond({ error: "Já existe uma análise do WhatsApp em andamento." })
    return false
  }
  analysisInProgress = true
  requestAnalysis(request).then(
    () => respond({ error: null }),
    error => respond({ error: error instanceof Error ? error.message : "Falha na análise do WhatsApp Web." })
  ).finally(() => {
    analysisInProgress = false
  })
  return true
})

async function tabRequest(tabId, request, attempts = 1) {
  for (let index = 0; index < attempts; index += 1) {
    try { return await chrome.tabs.sendMessage(tabId, request) }
    catch (error) {
      if (index + 1 === attempts) throw error
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }
}

async function processNextCommand() {
  if (commandInProgress || analysisInProgress || connectedTabId === null) return
  commandInProgress = true
  let command
  try {
    command = (await bridgePost("commands/next")).command
    if (!command) return
    if (!['read', 'send'].includes(command.action) || !/^[1-9][0-9]{7,14}$/.test(command.phone)
        || command.expires_at * 1000 <= Date.now()) throw new Error("invalid_command")
    activeCommand = command
    const tabId = connectedTabId
    const prepared = await tabRequest(tabId, { type: "kiara-whatsapp-prepare-command" })
    if (!prepared?.ready || prepared.hasDraft) throw new Error("human_draft_or_offline")
    if (prepared.phone !== command.phone) {
      await chrome.tabs.update(tabId, {
        url: `https://web.whatsapp.com/send?phone=${encodeURIComponent(command.phone)}`,
      })
      // Navigation retains the same logged-in Chrome session. Only readiness is retried.
      await new Promise(resolve => setTimeout(resolve, 1000))
      for (let index = 0; index < 35; index += 1) {
        if (command.expires_at * 1000 <= Date.now()) throw new Error("expired_command")
        try {
          const ready = await tabRequest(tabId, { type: "kiara-whatsapp-prepare-command" })
          if (ready?.ready && ready.phone === command.phone) break
          if (index === 34) throw new Error("identity_not_verified")
        } catch (error) { if (index === 34) throw error }
        await new Promise(resolve => setTimeout(resolve, 500))
      }
    }
    // Never retry an action, particularly after a send whose response might be lost.
    const result = await tabRequest(tabId, { type: "kiara-whatsapp-command", command })
    await bridgePost("commands/result", { ...result, id: command.id, phone: command.phone })
  } catch {
    if (command?.id) {
      await bridgePost("commands/result", { id: command.id, phone: command.phone, ok: false }).catch(() => {})
    }
  } finally {
    activeCommand = null
    commandInProgress = false
  }
}

chrome.tabs.onRemoved.addListener(tabId => {
  if (tabId === connectedTabId) connectedTabId = null
})
