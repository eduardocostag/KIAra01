import type { Workflow } from "./catalog"

/** A flow as the server keeps it: same shape as the editor's, plus activation and schedule. */
export type ServerFlow = Workflow & { enabled: boolean; next_run_at: string | null; version: number }

export type ServerStep = { node_id: string; type?: string; status: "done" | "blocked" | "error" | "approval" | "waiting"; output?: string; message?: string; at?: string }
export type ServerRun = {
  id: string; flow_id: string; flow_name: string; trigger: "manual" | "schedule" | "lead"
  status: "queued" | "running" | "waiting" | "done" | "partial" | "failed"
  steps: ServerStep[]; error: string | null; created_at: string; finished_at: string | null
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...init.headers } })
  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = payload && typeof payload === "object" ? (payload as { error?: { message?: unknown } }).error : null
    throw new Error(typeof error?.message === "string" ? error.message : `O servidor não concluiu a operação (HTTP ${response.status}).`)
  }
  return payload as T
}

const isFlow = (value: unknown): value is ServerFlow => {
  const item = value as ServerFlow | null
  return Boolean(item && typeof item.id === "string" && Array.isArray(item.nodes) && Array.isArray(item.edges))
}

export async function listServerFlows(): Promise<ServerFlow[]> {
  const data = await request<{ items?: unknown[] }>("/api/automation/flows")
  return (data.items ?? []).filter(isFlow)
}

export async function saveServerFlow(flow: Workflow, enabled: boolean): Promise<ServerFlow> {
  const definition = {
    nodes: flow.nodes.map(({ id, type, x, y, config }) => ({ id, type, x, y, config })),
    edges: flow.edges.map(({ id, from, to, port }) => ({ id, from, to, ...(port ? { port } : {}) })),
  }
  return request<ServerFlow>(`/api/automation/flows/${encodeURIComponent(flow.id)}`, {
    method: "PUT", body: JSON.stringify({ name: flow.name.trim() || "Fluxo sem nome", definition, enabled }),
  })
}

export async function deleteServerFlow(id: string): Promise<void> {
  await request(`/api/automation/flows/${encodeURIComponent(id)}`, { method: "DELETE" })
}

export async function runOnServer(id: string): Promise<{ run_id: string }> {
  return request(`/api/automation/flows/${encodeURIComponent(id)}/run`, { method: "POST" })
}

export async function listServerRuns(flowId?: string): Promise<ServerRun[]> {
  const data = await request<{ items?: ServerRun[] }>(`/api/automation/runs${flowId ? `?flow=${encodeURIComponent(flowId)}` : ""}`)
  return data.items ?? []
}

export const runStatusLabels: Record<ServerRun["status"], string> = {
  queued: "Na fila", running: "Executando", waiting: "Aguardando", done: "Concluída", partial: "Concluída com avisos", failed: "Falhou",
}
export const triggerLabels: Record<ServerRun["trigger"], string> = { manual: "Manual", schedule: "Agendamento", lead: "Novo lead" }
