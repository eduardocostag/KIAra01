import { kiaraApi } from "@/lib/api/server-client"

export async function GET(request: Request) {
  const flow = new URL(request.url).searchParams.get("flow")
  return kiaraApi(`/v1/automation/runs${flow ? `?flow=${encodeURIComponent(flow)}` : ""}`)
}
