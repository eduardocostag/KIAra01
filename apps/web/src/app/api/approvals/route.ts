import { kiaraApi } from "@/lib/api/server-client"

export async function GET(request: Request) {
  const status = new URL(request.url).searchParams.get("status") === "history" ? "history" : "pending"
  return kiaraApi(`/v1/approvals?status=${status}`)
}
