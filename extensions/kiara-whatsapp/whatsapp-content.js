(() => {
  const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))
  const phonePattern = /(?:true|false)_([0-9]{8,15})@(?:c\.us|s\.whatsapp\.net)_/
  let operationInProgress = false

  async function chatPhone(messages) {
    const peers = new Set()
    for (const message of messages) {
      const match = phonePattern.exec(message.id)
      if (match) peers.add(match[1])
    }
    if (peers.size === 1) return [...peers][0]

    const header = document.querySelector("#main header")
    if (!header) return null
    header.click()
    try {
      const panel = await waitFor(() => document.querySelector(
        "[data-testid='drawer-right'], [data-testid='contact-info-drawer']"
      ), 5000)
      const candidates = panel.innerText.match(/\+[0-9][0-9 ()-]{7,25}[0-9]/g) || []
      const phones = new Set(candidates.map(value => value.replace(/\D/g, "")).filter(
        value => /^[1-9][0-9]{7,14}$/.test(value)
      ))
      return phones.size === 1 ? [...phones][0] : null
    } catch {
      return null
    } finally {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
    }
  }

  function waitFor(read, timeout) {
    const started = Date.now()
    return new Promise((resolve, reject) => {
      const check = () => {
        const value = read()
        if (value) return resolve(value)
        if (Date.now() - started >= timeout) return reject(new Error("WhatsApp Web indisponível"))
        setTimeout(check, 100)
      }
      check()
    })
  }

  function readMessages() {
    const seen = new Set()
    return [...document.querySelectorAll("#main [data-id]")].flatMap(element => {
      const id = element.getAttribute("data-id")
      if (!id || seen.has(id)) return []
      const bubble = element.matches(".message-in,.message-out")
        ? element
        : element.querySelector(".message-in,.message-out") || element.closest(".message-in,.message-out")
      if (!bubble) return []
      seen.add(id)
      const text = [...bubble.querySelectorAll(".selectable-text.copyable-text")]
        .map(item => item.innerText).join("\n").trim().slice(0, 10000)
      return [{ id, direction: bubble.classList.contains("message-out") ? "out" : "in", text }]
    })
  }

  async function scan(limit) {
    const side = document.querySelector("#pane-side")
    if (!side) throw new Error("O WhatsApp Web ainda não está conectado. Entre na sua conta e tente novamente.")
    const initial = [...side.querySelectorAll("[data-testid='cell-frame-container']")].slice(0, limit)
    if (!initial.length) throw new Error("Não encontrei conversas visíveis na lista do WhatsApp.")
    const labels = initial.map(cell =>
      cell.querySelector("[data-testid='cell-frame-title']")?.innerText?.trim()
      || cell.getAttribute("aria-label") || ""
    )
    const conversations = []
    let skipped = 0
    for (let index = 0; index < initial.length; index += 1) {
      const cells = [...document.querySelectorAll("#pane-side [data-testid='cell-frame-container']")]
      const cell = cells[index]
      if (!cell || !cell.getClientRects().length) {
        skipped += 1
        continue
      }
      cell.click()
      try {
        await waitFor(() => document.querySelector("#main footer [contenteditable='true'][role='textbox']"), 12000)
      } catch {
        skipped += 1
        continue
      }
      await sleep(250)
      const messages = readMessages()
      if (!messages.some(message => message.direction === "in" && message.text)) {
        skipped += 1
        continue
      }
      const phone = await chatPhone(messages)
      if (!phone) {
        skipped += 1
        continue
      }
      const name = document.querySelector("#main header span[dir='auto']")?.innerText?.trim()
        || labels[index] || phone
      conversations.push({ phone, name: name.slice(0, 160), messages: messages.slice(-20).map(
        message => ({ ...message, text: message.text.slice(0, 2000) })
      ) })
    }
    return { scanned: initial.length, skipped, conversations }
  }

  chrome.runtime.onMessage.addListener((request, _sender, respond) => {
    if (request?.type === "kiara-whatsapp-prepare-command") {
      const composer = document.querySelector("#main footer [contenteditable='true'][role='textbox']")
      chatPhone(readMessages()).then(phone => respond({
        ready: Boolean(document.querySelector("#pane-side")), phone,
        hasDraft: Boolean(composer?.innerText?.trim()),
      }), () => respond({ ready: false }))
      return true
    }
    if (request?.type === "kiara-whatsapp-command") {
      if (operationInProgress) { respond({ ok: false }); return false }
      operationInProgress = true
      executeCommand(request.command).then(respond, () => respond({ ok: false })).finally(() => {
        operationInProgress = false
      })
      return true
    }
    if (request?.type === "kiara-whatsapp-status") {
      respond({ ready: Boolean(document.querySelector("#pane-side")) })
      return false
    }
    if (request?.type !== "kiara-scan-whatsapp") return false
    scan(Math.max(1, Math.min(30, Number(request.limit) || 30))).then(
      result => respond({ ok: true, result }),
      error => respond({ ok: false, error: error instanceof Error ? error.message : "Não foi possível ler o WhatsApp Web." })
    )
    return true
  })

  async function executeCommand(command) {
    if (!command || !['read', 'send'].includes(command.action)
        || !/^[1-9][0-9]{7,14}$/.test(command.phone)
        || command.expires_at * 1000 <= Date.now()) throw new Error("invalid_command")
    const messages = readMessages().slice(-100)
    if (await chatPhone(messages) !== command.phone) throw new Error("identity_mismatch")
    if (command.action === 'read') return { ok: true, messages }
    if (typeof command.text !== 'string' || !command.text.trim() || command.text.length > 4000
        || !Array.isArray(command.expected_ids)) throw new Error("invalid_send")
    const expected = new Set(command.expected_ids)
    const sameIds = current => current.length === expected.size && current.every(item => expected.has(item.id))
    if (!sameIds(messages)) throw new Error("conversation_changed")
    const composer = document.querySelector("#main footer [contenteditable='true'][role='textbox']")
    if (!composer || composer.innerText.trim()) throw new Error("human_draft")
    const changedByHuman = event => { if (event.isTrusted) interrupted = true }
    let interrupted = false
    document.addEventListener('pointerdown', changedByHuman, true)
    document.addEventListener('keydown', changedByHuman, true)
    let filled = false
    try {
      composer.focus()
      if (!document.execCommand('insertText', false, command.text)) throw new Error("composer_unavailable")
      filled = true
      composer.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: command.text }))
      await sleep(150)
      if (interrupted || composer.innerText.trim() !== command.text.trim()
          || await chatPhone(readMessages()) !== command.phone
          || !sameIds(readMessages().slice(-100))) throw new Error("conversation_changed")
      const authorized = await chrome.runtime.sendMessage({
        type: 'kiara-whatsapp-authorize', id: command.id, phone: command.phone,
      })
      if (!authorized?.allowed || interrupted || command.expires_at * 1000 <= Date.now()
          || await chatPhone(readMessages()) !== command.phone
          || document.querySelector("#main footer [contenteditable='true'][role='textbox']") !== composer
          || !sameIds(readMessages().slice(-100))) throw new Error("authorization_expired")
      const send = document.querySelector("#main footer [data-testid='compose-btn-send'], #main footer button[aria-label='Enviar'], #main footer button[aria-label='Send'], #main footer [data-icon='send']")
      if (!send || !composer.isConnected) throw new Error("send_unavailable")
      const sendButton = send.closest('button') || send
      sendButton.click()
      filled = false // After clicking, outcome may be uncertain; never erase or click again.
      for (let index = 0; index < 20; index += 1) {
        await sleep(300)
        const after = readMessages()
        if (await chatPhone(after) !== command.phone) throw new Error("identity_changed")
        const sent = after.find(item => !expected.has(item.id) && item.direction === 'out'
          && item.text.trim() === command.text.trim())
        if (sent) return { ok: true, message_id: sent.id }
      }
      throw new Error("send_unconfirmed")
    } finally {
      document.removeEventListener('pointerdown', changedByHuman, true)
      document.removeEventListener('keydown', changedByHuman, true)
      if (filled && !interrupted && composer.isConnected && composer.innerText.trim() === command.text.trim()) {
        composer.textContent = ''
        composer.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward' }))
      }
    }
  }

  const heartbeat = () => {
    chrome.runtime.sendMessage({ type: "kiara-whatsapp-heartbeat", ready: Boolean(document.querySelector("#pane-side")) }).catch(() => {})
  }
  heartbeat()
  setInterval(heartbeat, 10000)
})()
