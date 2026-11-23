/**
 * Which Kiara modules each account may use. The system administrators choose them per user in
 * Administração → Usuários; the choice lives in the account's Supabase `app_metadata.modules`, which only the
 * server (service role) can write and which travels inside the session token. No database table involved.
 *
 * Shared by the proxy, server pages and the admin screen, so nothing here may import server-only code.
 */
export type ModuleKey = "leads" | "whatsapp" | "chat" | "automation"

export type ModuleInfo = { key: ModuleKey; label: string; description: string; href: string }

export const MODULES: readonly ModuleInfo[] = [
  { key: "leads", label: "KIARA Leads", description: "Pesquisa, CRM e Pipeline.", href: "/app/leads" },
  { key: "whatsapp", label: "KIARA WhatsApp", description: "Conexão, análise e automação.", href: "/app/whatsapp" },
  { key: "chat", label: "KIARA Chat", description: "Conversa, voz e criação com IA.", href: "/app/chat" },
  { key: "automation", label: "KIARA Automation", description: "Fluxos, tarefas, agenda, redes e anúncios.", href: "/app/automation" },
]

export const MODULE_KEYS: readonly ModuleKey[] = MODULES.map((item) => item.key)

/** Accounts the administrator never configured keep what they already used before per-user modules: Kiara Leads. */
export const DEFAULT_MODULES: readonly ModuleKey[] = ["leads"]

/** Every system administrator (full access); keep in sync with services/api/kiara_api/admins.py. */
export const SYSTEM_ADMIN_EMAILS: readonly string[] = ["admin@kiara.local", "eduardocgonsalves@hotmail.com"]

export function isSystemAdminEmail(email: string | null | undefined): boolean {
  return Boolean(email) && SYSTEM_ADMIN_EMAILS.includes(email!.trim().toLowerCase())
}

export function isModuleKey(value: unknown): value is ModuleKey {
  return typeof value === "string" && (MODULE_KEYS as readonly string[]).includes(value)
}

/** The modules stored for an account (in the product's order), or the default when none were ever chosen. */
export function storedModules(appMetadata: unknown): ModuleKey[] {
  const raw = appMetadata && typeof appMetadata === "object" ? (appMetadata as { modules?: unknown }).modules : undefined
  if (!Array.isArray(raw)) return [...DEFAULT_MODULES]
  return MODULE_KEYS.filter((key) => raw.includes(key))
}

/** What an account may open: administrators everything, everyone else what the administrator chose. */
export function modulesFor(email: string | null | undefined, appMetadata: unknown): ModuleKey[] {
  return isSystemAdminEmail(email) ? [...MODULE_KEYS] : storedModules(appMetadata)
}

const LEADS_PAGES = ["leads", "hunter", "pipeline", "concorrencia", "conteudo", "followups", "fila"]

/** The module a page belongs to; shared pages (settings, approvals, company, team, plan) belong to none. */
export function moduleForPage(pathname: string): ModuleKey | null {
  const under = (path: string) => pathname === `/app/${path}` || pathname.startsWith(`/app/${path}/`)
  if (under("chat")) return "chat"
  if (under("automation")) return "automation"
  if (under("whatsapp") || under("inbox")) return "whatsapp"
  return LEADS_PAGES.some(under) ? "leads" : null
}

const API_MODULES: readonly (readonly [string, ModuleKey])[] = [
  ["/v1/chat", "chat"], ["/v1/whatsapp-web", "whatsapp"], ["/v1/automation", "automation"],
]

/** The module a backend route belongs to (the site's proxy only forwards it to accounts with that module). */
export function moduleForApiPath(path: string): ModuleKey | null {
  return API_MODULES.find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`))?.[1] ?? null
}
