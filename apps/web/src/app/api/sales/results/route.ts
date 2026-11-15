import { kiaraApi } from "@/lib/api/server-client"

export async function GET(request: Request) {
  const days = Number(new URL(request.url).searchParams.get("days") ?? 30)
  if (!Number.isInteger(days) || days < 7 || days > 365) return Response.json({ error: { message: "Período inválido." } }, { status: 400 })
  return kiaraApi(`/v1/sales/results?days=${days}`)
}
