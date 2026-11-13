import { kiaraApi } from "@/lib/api/server-client"
import { requireWorkspace } from "@/lib/auth"
import { createClient } from "@/lib/supabase/server"

const headers = { "Cache-Control": "no-store, private", "Pragma": "no-cache" }

function rejected(status: number) {
  return Response.json({ error: { message: "Conexão não autorizada." } }, { status, headers })
}

/** Short in-memory executor lease; never exports the browser refresh token. */
export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) return rejected(403)
  try {
    // Chat and WhatsApp are in early access: only the system administrator gets a lease.
    const workspace = await requireWorkspace().catch(() => null)
    if (!workspace) return rejected(401)
    if (!workspace.isSystemAdmin) return rejected(403)
    const supabase = await createClient()
    const { data, error } = await supabase.auth.getSession()
    const session = data.session
    if (error || !session?.access_token) return rejected(401)
    const { data: identity, error: identityError } = await supabase.auth.getUser(session.access_token)
    if (identityError || !identity.user) return rejected(401)

    // The API owns organization membership; the website's synthetic role is not authority.
    const response = await kiaraApi("/v1/me")
    if (!response.ok) return rejected(response.status === 401 || response.status === 403 ? response.status : 503)
    const membership = await response.json()
    if (membership.user_id !== identity.user.id || !["owner", "admin"].includes(membership.role)) return rejected(403)
    const expiresAt = Math.min(session.expires_at ?? 0, Math.floor(Date.now() / 1000) + 90)
    if (expiresAt <= Math.floor(Date.now() / 1000) + 5) return rejected(401)
    return Response.json({ access_token: session.access_token, expires_at: expiresAt }, { headers })
  } catch {
    // Do not expose identity-provider response bodies or credentials in errors/logs.
    return rejected(503)
  }
}
