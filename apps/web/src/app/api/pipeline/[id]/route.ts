import { kiaraApi } from "@/lib/api/server-client"

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  let body: unknown
  try { body = await request.json() } catch {
    return Response.json({ error: { message: "Dados inválidos. Recarregue e tente novamente." } }, { status: 400 })
  }
  return kiaraApi(`/v1/pipeline/${encodeURIComponent(id)}`, {
    method: "PATCH", body: JSON.stringify(body), headers: {
      "If-Match": request.headers.get("if-match") ?? "",
      "Idempotency-Key": request.headers.get("idempotency-key") ?? "",
    },
  })
}
