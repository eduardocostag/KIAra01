import { AdministratorRequiredError, AuthenticationRequiredError, isSystemAdminEmail, requireSystemAdmin } from "@/lib/auth"
import { kiaraApi } from "@/lib/api/server-client"
import { createAdminClient } from "@/lib/supabase/admin"
import { isModuleKey, MODULE_KEYS, storedModules } from "@/lib/modules"

/** Administração → Usuários: full control of an account, for the system administrators only.
 *  Actions: set a new password, end every session, block / unblock access, delete the account, choose its modules.
 *  The administrator accounts themselves can get a new password or be signed out, never blocked or deleted. */
type Action = "password" | "sign_out" | "block" | "unblock" | "delete" | "modules"
const ACTIONS: Action[] = ["password", "sign_out", "block", "unblock", "delete", "modules"]
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type Context = { params: Promise<{ id: string }> }

async function endSessions(id: string): Promise<number> {
  const response = await kiaraApi(`/v1/admin/users/${id}/sign-out`, { method: "POST" })
  const body = await response.json().catch(() => null) as { ended_sessions?: number; error?: { message?: string } } | null
  if (!response.ok) throw new Error(body?.error?.message || "Não foi possível encerrar as sessões.")
  return body?.ended_sessions ?? 0
}

export async function POST(request: Request, { params }: Context) {
  try {
    const admin = await requireSystemAdmin()
    const { id } = await params
    if (!UUID.test(id)) return Response.json({ error: "Usuário inválido." }, { status: 400 })
    const body = await request.json().catch(() => null) as { action?: unknown; password?: unknown; modules?: unknown } | null
    const action = body?.action as Action
    if (!ACTIONS.includes(action)) return Response.json({ error: "Ação inválida." }, { status: 400 })

    const supabase = createAdminClient()
    const { data, error } = await supabase.auth.admin.getUserById(id)
    if (error || !data.user) return Response.json({ error: "Usuário não encontrado." }, { status: 404 })
    const target = data.user
    const protectedAccount = isSystemAdminEmail(target.email) || target.id === admin.userId
    if (protectedAccount && (action === "block" || action === "delete")) {
      return Response.json({ error: "Contas de administrador não podem ser bloqueadas nem excluídas por aqui." }, { status: 403 })
    }
    const who = target.email ?? "o usuário"

    if (action === "modules") {
      if (isSystemAdminEmail(target.email)) return Response.json({ error: "Administradores sempre têm todos os módulos." }, { status: 400 })
      if (!Array.isArray(body?.modules) || !body.modules.every(isModuleKey)) return Response.json({ error: "Módulos inválidos." }, { status: 400 })
      const chosen = MODULE_KEYS.filter((key) => (body.modules as unknown[]).includes(key))
      const before = storedModules(target.app_metadata)
      const { error: updateError } = await supabase.auth.admin.updateUserById(id, { app_metadata: { ...(target.app_metadata ?? {}), modules: chosen } })
      if (updateError) throw updateError
      // The modules travel inside the session: removing one signs the person out everywhere so it closes at once;
      // added ones appear on the next sign-in or within the hour, when the session renews itself.
      const removed = before.some((key) => !chosen.includes(key))
      if (removed) await endSessions(id)
      return Response.json({ ok: true, modules: chosen, message: removed
        ? `Módulos de ${who} atualizados. A pessoa foi desconectada e verá só os módulos novos ao entrar de novo.`
        : `Módulos de ${who} atualizados. Os novos aparecem no próximo acesso (ou em até 1 hora, se já estiver conectada).` })
    }

    if (action === "password") {
      const password = typeof body?.password === "string" ? body.password : ""
      if (password.length < 6 || password.length > 72) return Response.json({ error: "A senha precisa ter de 6 a 72 caracteres." }, { status: 400 })
      const { error: updateError } = await supabase.auth.admin.updateUserById(id, { password })
      if (updateError) throw updateError
      // The old password stops working everywhere: other devices must sign in again (except your own session).
      if (target.id !== admin.userId) await endSessions(id)
      return Response.json({ ok: true, message: `Senha de ${who} alterada.${target.id !== admin.userId ? " Os aparelhos conectados precisam entrar de novo." : ""}` })
    }
    if (action === "sign_out") {
      const ended = await endSessions(id)
      return Response.json({ ok: true, message: ended ? `${who} foi desconectado de ${ended} ${ended === 1 ? "aparelho" : "aparelhos"}.` : `${who} não tinha sessões abertas.` })
    }
    if (action === "block" || action === "unblock") {
      const { error: banError } = await supabase.auth.admin.updateUserById(id, { ban_duration: action === "block" ? "876000h" : "none" })
      if (banError) throw banError
      if (action === "block") await endSessions(id)
      return Response.json({ ok: true, message: action === "block" ? `${who} foi bloqueado e desconectado.` : `${who} foi desbloqueado e pode entrar de novo.` })
    }
    await endSessions(id).catch(() => 0)
    const { error: deleteError } = await supabase.auth.admin.deleteUser(id)
    if (deleteError) throw deleteError
    return Response.json({ ok: true, message: `A conta de ${who} foi excluída.` })
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) return Response.json({ error: "Sessão expirada." }, { status: 401 })
    if (error instanceof AdministratorRequiredError) return Response.json({ error: "Acesso exclusivo do administrador." }, { status: 403 })
    return Response.json({ error: error instanceof Error ? error.message : "Não foi possível concluir a ação." }, { status: 500 })
  }
}
