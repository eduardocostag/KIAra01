const leadPaths = ["leads", "hunter", "pipeline", "concorrencia", "conteudo", "followups", "settings", "admin"]
// Conversations belong to the attendance side (WhatsApp), not to prospecting.
const whatsappPaths = ["whatsapp", "inbox"]

export function modulePrefixForPath(pathname: string): string | null {
  if (pathname === "/app/chat" || pathname.startsWith("/app/chat/")) return "/app/chat"
  if (pathname === "/app/automation" || pathname.startsWith("/app/automation/")) return "/app/automation"
  if (whatsappPaths.some((path) => pathname === `/app/${path}` || pathname.startsWith(`/app/${path}/`))) return "/app/whatsapp"
  if (pathname === "/app/atendimento" || pathname.startsWith("/app/atendimento/")) return "/app/atendimento"
  if (pathname === "/app/ti" || pathname.startsWith("/app/ti/")) return "/app/ti"
  return leadPaths.some((path) => pathname === `/app/${path}` || pathname.startsWith(`/app/${path}/`)) ? "/app/leads" : null
}

export function isModuleNavActive(pathname: string, hash: string, href: string): boolean {
  const [path, section] = href.split("#")
  if (section) return pathname === path && hash === `#${section}`
  if (path === "/app/whatsapp" || path === "/app/chat") return pathname === path && !hash
  return pathname === path || pathname.startsWith(`${path}/`)
}
