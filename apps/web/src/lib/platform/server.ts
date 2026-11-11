import "server-only"
import { cache } from "react"
import { kiaraApi } from "@/lib/api/server-client"
import {
  parsePlatformContext,
  parsePlatformModuleDetail,
  parsePlatformSkills,
  type ModuleKey,
} from "./contracts"

export class PlatformApiError extends Error {
  constructor(readonly status: number, readonly requestId: string | null = null) {
    super(status === 403 || status === 404 ? "Acesso não autorizado a este módulo." : "Não foi possível consultar a plataforma.")
  }
}

async function readPlatform(path: string): Promise<unknown> {
  const response = await kiaraApi(path)
  const requestId = response.headers.get("X-Correlation-ID")
  if (!response.ok) throw new PlatformApiError(response.status, requestId)
  try { return await response.json() }
  catch { throw new PlatformApiError(502, requestId) }
}

// React cache deduplicates within this render request; it never shares a tenant's context across requests.
export const getPlatformContext = cache(async () => {
  const value = await readPlatform("/v1/platform/context")
  try { return parsePlatformContext(value) }
  catch { throw new PlatformApiError(502) }
})

export const getPlatformModule = cache(async (key: ModuleKey) => {
  const value = await readPlatform(`/v1/platform/modules/${key}`)
  try { return parsePlatformModuleDetail(value, key) }
  catch { throw new PlatformApiError(502) }
})

export const getPlatformSkills = cache(async () => {
  const value = await readPlatform("/v1/platform/skills")
  try { return parsePlatformSkills(value) }
  catch { throw new PlatformApiError(502) }
})
