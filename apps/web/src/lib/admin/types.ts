export type AdminUser = {
  id: string
  email: string
  name: string
  provider: string
  createdAt: string
  lastSignInAt: string | null
  isAdmin: boolean
}

export type AdminService = {
  id: string
  name: string
  category: "Plataforma" | "Pesquisa" | "Diretórios" | "Infraestrutura"
  status: "operational" | "attention" | "unavailable" | "unknown"
  detail: string
  configuration: string
}

export type AdminAuditEvent = {
  id: string
  action: string
  resourceType: string
  correlationId: string
  occurredAt: string
}

export type AdminSnapshot = {
  generatedAt: string
  users: AdminUser[]
  services: AdminService[]
  auditEvents: AdminAuditEvent[]
  notices: string[]
}
