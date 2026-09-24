const RESERVED = new Set(["about", "accounts", "api", "challenge", "developer", "directory", "direct", "emails", "explore", "legal", "p", "privacy", "reel", "reels", "stories", "web"])
const count = document.querySelector("#count")
const status = document.querySelector("#status")

function storedProfiles() {
  return new Promise((resolve) => chrome.storage.local.get({ profiles: [] }, ({ profiles }) => resolve(Array.isArray(profiles) ? profiles : [])))
}

async function refresh() { count.textContent = String((await storedProfiles()).length) }

document.querySelector("#capture").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id || !/^https:\/\/www\.instagram\.com\//i.test(tab.url || "")) {
    status.textContent = "Abra o Instagram nesta aba para capturar os perfis públicos."
    return
  }
  const [{ result = [] } = {}] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (reserved) => {
      const blocked = new Set(reserved)
      const found = new Map()
      const root = document.querySelector('[role="dialog"]') || document
      for (const anchor of root.querySelectorAll("a[href]")) {
        let url
        try { url = new URL(anchor.href, location.href) } catch { continue }
        if (url.hostname !== "www.instagram.com" && url.hostname !== "instagram.com") continue
        const parts = url.pathname.split("/").filter(Boolean)
        const username = parts[0] || ""
        if (parts.length !== 1 || blocked.has(username.toLowerCase()) || !/^[A-Za-z0-9._]{1,30}$/.test(username)) continue
        const label = (anchor.textContent || "").replace(/\s+/g, " ").trim()
        found.set(username.toLowerCase(), `@${username.toLowerCase()}${label && label.toLowerCase() !== username.toLowerCase() ? ` | ${label.slice(0, 120)}` : ""}`)
      }
      return [...found.values()]
    },
    args: [[...RESERVED]],
  })
  const prior = await storedProfiles()
  const merged = [...new Map([...prior, ...result].map((item) => [item.split("|")[0].trim().toLowerCase(), item])).values()]
  await chrome.storage.local.set({ profiles: merged })
  status.textContent = `${result.length} perfis visíveis encontrados; ${merged.length} únicos guardados.`
  await refresh()
})

document.querySelector("#copy").addEventListener("click", async () => {
  const profiles = await storedProfiles()
  if (!profiles.length) { status.textContent = "Capture alguns perfis antes de copiar."; return }
  await navigator.clipboard.writeText(profiles.join("\n"))
  status.textContent = "Lista copiada. Agora cole no campo da Kiara."
})

document.querySelector("#clear").addEventListener("click", async () => {
  await chrome.storage.local.set({ profiles: [] })
  status.textContent = "Lista local limpa."
  await refresh()
})

void refresh()
