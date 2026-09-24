import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth"
import { createClient } from "@/lib/supabase/server"

function validEmail(value: unknown): value is string {
  return typeof value === "string" && value.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

export async function POST(request: Request) {
  try {
    await requireSystemAdmin()
    const body: unknown = await request.json()
    const email = body && typeof body === "object" && "email" in body ? body.email : null
    if (!validEmail(email)) return Response.json({ error: "Informe um e-mail válido." }, { status: 400 })

    const origin = new URL(request.url).origin
    const supabase = await createClient()
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
      redirectTo: `${origin}/reset-password`,
    })
    if (error) throw error
    return Response.json({ ok: true, message: `E-mail de recuperação enviado para ${email}.` })
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) return Response.json({ error: "Sessão expirada." }, { status: 401 })
    if (error instanceof AdministratorRequiredError) return Response.json({ error: "Acesso exclusivo do administrador." }, { status: 403 })
    return Response.json({ error: error instanceof Error ? error.message : "Não foi possível enviar a recuperação de senha." }, { status: 500 })
  }
}
