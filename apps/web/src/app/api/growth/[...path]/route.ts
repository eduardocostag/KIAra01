import { kiaraApi } from "@/lib/api/server-client"

// One bridge for the growth features; only these API areas are reachable through it.
const ALLOWED = [/^knowledge(\/[\w-]{1,80})?$/, /^memory(\/[\w-]{1,80})?$/, /^team(\/(invites|members)\/[\w@.-]{1,200}|\/invites|\/accept)?$/, /^billing\/plan$/, /^sales\/(draft|presets(\/[a-z]{1,30})?)$/, /^presencial\/(read|contacts)$/]

async function forward(request: Request, params: Promise<{ path: string[] }>) {
  const path = (await params).path.join("/")
  if (!ALLOWED.some((pattern) => pattern.test(path))) return Response.json({ error: { message: "Recurso não encontrado." } }, { status: 404 })
  if (request.method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const body = request.method === "GET" || request.method === "DELETE" ? undefined : await request.text()
  if (body && body.length > 4_400_000) return Response.json({ error: { message: "Arquivo grande demais (máximo de 3 MB)." } }, { status: 413 })
  return kiaraApi(`/v1/${path}`, { method: request.method, ...(body ? { body } : {}) })
}

type Context = { params: Promise<{ path: string[] }> }
export const maxDuration = 120
export async function GET(request: Request, { params }: Context) { return forward(request, params) }
export async function POST(request: Request, { params }: Context) { return forward(request, params) }
export async function PUT(request: Request, { params }: Context) { return forward(request, params) }
export async function PATCH(request: Request, { params }: Context) { return forward(request, params) }
export async function DELETE(request: Request, { params }: Context) { return forward(request, params) }
