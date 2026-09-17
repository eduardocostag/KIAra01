import { kiaraApi } from "@/lib/api/server-client"

export async function DELETE(request: Request) {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return Response.json(
      { error: { code: "invalid_request", message: "Confirmação inválida." } },
      { status: 400 },
    )
  }
  return kiaraApi("/v1/workspace/commercial-data", {
    method: "DELETE",
    body: JSON.stringify(body),
  })
}
