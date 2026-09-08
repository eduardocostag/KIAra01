import { kiaraApi } from "@/lib/api/server-client"
export async function GET() { return kiaraApi("/v1/hunter/searches") }
export async function POST(request: Request) { return kiaraApi("/v1/hunter/searches", { method: "POST", body: await request.text() }) }
