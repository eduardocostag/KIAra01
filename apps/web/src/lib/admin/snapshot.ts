import "server-only"

import { SYSTEM_ADMIN_EMAIL } from "@/lib/auth"
import { createAdminClient, hasSupabaseAdminConfig } from "@/lib/supabase/admin"
import type { AdminAuditEvent, AdminService, AdminSnapshot, AdminUser } from "./types"

type Health = { live: boolean; ready: boolean; detail: string }

async function backendHealth(): Promise<Health> {
  const configured = process.env.KIARA_API_URL?.trim()
  if (!configured) return { live: false, ready: false, detail: "KIARA_API_URL não configurada." }

  try {
    const base = new URL(configured)
    const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET?.trim()
    const requestOptions: RequestInit = {
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
      headers: bypass ? { "x-vercel-protection-bypass": bypass } : undefined,
    }
    const [live, ready] = await Promise.all([
      fetch(new URL("health/live", base.href.endsWith("/") ? base : `${base.href}/`), requestOptions),
      fetch(new URL("health/ready", base.href.endsWith("/") ? base : `${base.href}/`), requestOptions),
    ])
    return {
      live: live.ok,
      ready: ready.ok,
      detail: ready.ok ? "API e banco responderam ao diagnóstico." : `API respondeu, mas a prontidão retornou HTTP ${ready.status}.`,
    }
  } catch (error) {
    return { live: false, ready: false, detail: error instanceof Error ? `API sem resposta: ${error.message}` : "API sem resposta." }
  }
}

async function loadUsers(notices: string[]): Promise<AdminUser[]> {
  if (!hasSupabaseAdminConfig()) {
    notices.push("A gestão de usuários requer SUPABASE_SERVICE_ROLE_KEY no ambiente do site.")
    return []
  }
  try {
    const { data, error } = await createAdminClient().auth.admin.listUsers({ page: 1, perPage: 200 })
    if (error) throw error
    return data.users.map((user) => {
      const metadata = user.user_metadata ?? {}
      const name = [metadata.first_name, metadata.last_name].filter((value) => typeof value === "string" && value.trim()).join(" ")
        || (typeof metadata.full_name === "string" ? metadata.full_name : "")
      return {
        id: user.id,
        email: user.email ?? "E-mail não informado",
        name: name || "Usuário",
        provider: user.app_metadata?.provider === "google" ? "Google" : "E-mail e senha",
        createdAt: user.created_at,
        lastSignInAt: user.last_sign_in_at ?? null,
        isAdmin: user.email?.trim().toLowerCase() === SYSTEM_ADMIN_EMAIL,
      }
    })
  } catch (error) {
    notices.push(error instanceof Error ? `Usuários: ${error.message}` : "Não foi possível consultar os usuários.")
    return []
  }
}

async function loadAuditEvents(notices: string[]): Promise<AdminAuditEvent[]> {
  if (!hasSupabaseAdminConfig()) return []
  try {
    const { data, error } = await createAdminClient()
      .from("audit_events")
      .select("id,action,resource_type,correlation_id,occurred_at")
      .order("occurred_at", { ascending: false })
      .limit(40)
    if (error) throw error
    return (data ?? []).map((event) => ({
      id: String(event.id),
      action: String(event.action),
      resourceType: String(event.resource_type),
      correlationId: String(event.correlation_id),
      occurredAt: String(event.occurred_at),
    }))
  } catch {
    notices.push("Os logs de auditoria do backend não estão publicados no banco de autenticação; o diagnóstico técnico continua disponível abaixo.")
    return []
  }
}

function serviceInventory(health: Health): AdminService[] {
  const authConfigured = Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()
    && (process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)?.trim(),
  )
  const adminConfigured = hasSupabaseAdminConfig()
  const apiConfigured = Boolean(process.env.KIARA_API_URL?.trim())

  return [
    { id: "auth", name: "Autenticação Supabase", category: "Plataforma", status: authConfigured ? "operational" : "unavailable", detail: authConfigured ? "Login e sessões configurados." : "Login indisponível por falta de credenciais públicas.", configuration: "NEXT_PUBLIC_SUPABASE_URL + chave publicável" },
    { id: "users", name: "Administração de usuários", category: "Plataforma", status: adminConfigured ? "operational" : "attention", detail: adminConfigured ? "Listagem e recuperação de senha habilitadas." : "Apenas o gerenciamento administrativo está indisponível.", configuration: "SUPABASE_SERVICE_ROLE_KEY" },
    { id: "api", name: "API Kiara", category: "Infraestrutura", status: health.live ? "operational" : "unavailable", detail: apiConfigured ? health.detail : "O endereço do backend não foi informado.", configuration: "KIARA_API_URL" },
    { id: "database", name: "Banco comercial", category: "Infraestrutura", status: health.ready ? "operational" : health.live ? "attention" : "unknown", detail: health.ready ? "Pronto para pesquisas, leads e anotações." : "Sem confirmação de prontidão pelo backend.", configuration: "POSTGRES_URL no projeto da API" },
    { id: "web", name: "Pesquisa Web", category: "Pesquisa", status: health.ready ? "operational" : "unknown", detail: health.ready ? "Motor público e enriquecimento disponíveis." : "Aguardando confirmação da API.", configuration: "EXA_API_KEY e FIRECRAWL_API_KEY são aceleradores opcionais" },
    { id: "maps", name: "Google Maps e diretórios", category: "Diretórios", status: health.ready ? "operational" : "unknown", detail: health.ready ? "Busca gratuita por diretórios está disponível; Places é opcional." : "Aguardando confirmação da API.", configuration: "GOOGLE_PLACES_API_KEY é opcional" },
    { id: "meta", name: "Instagram e Facebook públicos", category: "Pesquisa", status: health.ready ? "operational" : "unknown", detail: "Descoberta pública disponível; dados privados exigem conexão oficial Meta.", configuration: "Conexão Instagram na seção Integrações" },
    { id: "scrapling", name: "Scrapling", category: "Pesquisa", status: health.ready ? "operational" : "unknown", detail: health.ready ? "Adaptador de leitura pública instalado no backend." : "O código está instalado, mas o backend não confirmou prontidão.", configuration: "services/api/kiara_api/scraping_adapters.py" },
    { id: "browser", name: "Navegação avançada", category: "Pesquisa", status: "unknown", detail: "Recurso opcional; o site não recebe nem expõe a chave do backend.", configuration: "BROWSERBASE_API_KEY + BROWSERBASE_PROJECT_ID no projeto da API" },
    { id: "obscura", name: "Obscura CDP", category: "Pesquisa", status: "unknown", detail: "Conector opcional para sessões de navegador gerenciadas.", configuration: "OBSCURA_CDP_URL + OBSCURA_AUTH_TOKEN no projeto da API" },
  ]
}

export async function getAdminSnapshot(): Promise<AdminSnapshot> {
  const notices: string[] = []
  const [health, users, auditEvents] = await Promise.all([
    backendHealth(),
    loadUsers(notices),
    loadAuditEvents(notices),
  ])
  return {
    generatedAt: new Date().toISOString(),
    users,
    services: serviceInventory(health),
    auditEvents,
    notices,
  }
}
