import { kiaraApi } from "@/lib/api/server-client"
import { isModuleKey } from "@/lib/platform/contracts"

export async function GET(_request: Request, { params }: { params: Promise<{ moduleKey: string }> }) {
  const { moduleKey } = await params
  if (!isModuleKey(moduleKey)) return Response.json({ error: { code: "platform_module_not_found", message: "Módulo desconhecido.", request_id: crypto.randomUUID(), details: {} } }, { status: 404, headers: { "Cache-Control": "no-store" } })
  return kiaraApi(`/v1/platform/modules/${moduleKey}`)
}
