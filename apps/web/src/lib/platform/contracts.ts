/** Read-only platform contracts. No tenant or permission is inferred in the browser. */
export const moduleKeys = ["leads", "whatsapp", "atendimento", "ti", "intelligence"] as const
export type ModuleKey = typeof moduleKeys[number]
export type PlatformRole = "client" | "reseller" | "platform_admin"

export type PlatformModule = Readonly<{
  key: ModuleKey
  name: string
  description: string
  href: string
  status: "operational" | "preparation"
  status_label: string
  enabled: true
  areas: readonly string[]
  integration_status: "existing" | "pending"
}>
export type PlatformContext = Readonly<{
  brand: "KIARA"
  organization: Readonly<{ id: string; name: string }>
  membership: Readonly<{ id: string; role: string }>
  platform_role: PlatformRole
  modules: readonly PlatformModule[]
  phase: "structure_only"
  external_execution_enabled: false
  access_source: string
}>
export type PlatformModuleDetail = Readonly<{
  module: PlatformModule
  phase: "structure_only"
  external_execution_enabled: false
  execution_status: "inactive"
}>
export type PlatformSkill = Readonly<{
  name: string
  description: string
  modules: readonly ModuleKey[]
  trust: "untrusted_reference"
  executor_status: "inactive"
}>

export function isModuleKey(value: unknown): value is ModuleKey {
  return typeof value === "string" && moduleKeys.some((key) => key === value)
}

export function moduleHref(key: ModuleKey): string {
  return key === "leads" ? "/app" : `/app/platform/${key}`
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Resposta da plataforma inválida.")
  return value as Record<string, unknown>
}

function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) throw new Error("Dados da plataforma incompletos.")
  return value
}

function structure(value: Record<string, unknown>) {
  if (value.phase !== "structure_only" || value.external_execution_enabled !== false) {
    throw new Error("Estado da plataforma incompatível com esta etapa.")
  }
}

function role(value: unknown): PlatformRole {
  if (value !== "client" && value !== "reseller" && value !== "platform_admin") throw new Error("Papel da plataforma inválido.")
  return value
}

export function parsePlatformModule(value: unknown): PlatformModule {
  const data = object(value)
  if (!isModuleKey(data.key) || data.enabled !== true || data.href !== moduleHref(data.key)) {
    throw new Error("Módulo indisponível ou endereço inválido.")
  }
  const operational = data.key === "leads"
  const status = operational ? "operational" : "preparation"
  const integrationStatus = operational ? "existing" : "pending"
  if (data.status !== status || data.integration_status !== integrationStatus) {
    throw new Error("Estado do módulo incompatível com esta etapa.")
  }
  if (!Array.isArray(data.areas)) throw new Error("Áreas do módulo inválidas.")
  return {
    key: data.key, name: text(data.name), description: text(data.description), href: data.href,
    status, status_label: text(data.status_label), enabled: true,
    areas: data.areas.map(text), integration_status: integrationStatus,
  }
}

export function parsePlatformContext(value: unknown): PlatformContext {
  const data = object(value)
  structure(data)
  if (data.brand !== "KIARA" || !Array.isArray(data.modules)) throw new Error("Contexto da plataforma inválido.")
  const organization = object(data.organization)
  const membership = object(data.membership)
  const modules = data.modules.map(parsePlatformModule)
  if (new Set(modules.map((module) => module.key)).size !== modules.length) throw new Error("Módulos duplicados na plataforma.")
  return {
    brand: "KIARA", organization: { id: text(organization.id), name: text(organization.name) },
    membership: { id: text(membership.id), role: text(membership.role) },
    platform_role: role(data.platform_role), modules, phase: "structure_only",
    external_execution_enabled: false, access_source: text(data.access_source),
  }
}

export function parsePlatformModuleDetail(value: unknown, expectedKey: ModuleKey): PlatformModuleDetail {
  const data = object(value)
  structure(data)
  const descriptor = parsePlatformModule(data.module)
  if (descriptor.key !== expectedKey || data.execution_status !== "inactive") throw new Error("Acesso ao módulo não confirmado.")
  return { module: descriptor, phase: "structure_only", external_execution_enabled: false, execution_status: "inactive" }
}

export function parsePlatformSkills(value: unknown): readonly PlatformSkill[] {
  const data = object(value)
  structure(data)
  if (!Array.isArray(data.items)) throw new Error("Catálogo de skills inválido.")
  const skills: PlatformSkill[] = data.items.map((value) => {
    const item = object(value)
    if (!Array.isArray(item.modules) || item.modules.length === 0 ||
      item.trust !== "untrusted_reference" || item.executor_status !== "inactive") throw new Error("Skill inválida ou executora ativa.")
    const modules = item.modules.map((module): ModuleKey => {
      if (!isModuleKey(module)) throw new Error("Escopo de módulo inválido.")
      return module
    })
    if (new Set(modules).size !== modules.length) throw new Error("Escopos de módulo duplicados.")
    return {
      name: text(item.name),
      description: text(item.description),
      modules,
      trust: "untrusted_reference",
      executor_status: "inactive",
    }
  })
  if (new Set(skills.map((skill) => skill.name)).size !== skills.length) {
    throw new Error("Skills duplicadas no catálogo.")
  }
  return skills
}

export const platformRoleLabels: Record<PlatformRole, string> = {
  client: "Cliente", reseller: "Revendedor", platform_admin: "Administrador da plataforma",
}

export function platformFailureKind(status: number): "authentication" | "denied" | "unavailable" {
  return status === 401 ? "authentication" : status === 403 || status === 404 ? "denied" : "unavailable"
}
