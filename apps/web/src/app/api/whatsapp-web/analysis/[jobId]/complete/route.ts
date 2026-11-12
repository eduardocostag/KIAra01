import { kiaraApi } from "@/lib/api/server-client"

/** Records the result of a WhatsApp analysis read by the local bridge (QR session) into the CRM. */
export async function POST(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const { jobId } = await params
  let body: unknown
  try { body = await request.json() } catch {
    return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 })
  }
  // The API validates the payload, the caller's role and the job ownership.
  return kiaraApi(`/v1/whatsapp-web/analysis/${encodeURIComponent(jobId)}/complete`, { method: "POST", body: JSON.stringify(body) })
}
