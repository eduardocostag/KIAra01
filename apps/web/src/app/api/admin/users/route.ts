import { AdministratorRequiredError, AuthenticationRequiredError, isSystemAdminEmail, requireSystemAdmin } from "@/lib/auth"
import type { AdminUser } from "@/lib/admin/types"
import { createAdminClient } from "@/lib/supabase/admin"
import { isModuleKey, MODULE_KEYS } from "@/lib/modules"

/** Administração → Usuários → "Novo usuário": the system administrators create an account that can sign in right away.
 *  A plain user name ("kiara01") becomes kiara01@kiara.local, which the sign-in form accepts as just "kiara01". */
const USER_NAME = /^[a-z0-9][a-z0-9._-]{1,39}$/
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(request: Request) {
  try {
    await requireSystemAdmin()
    const body = await request.json().catch(() => null) as { login?: unknown; password?: unknown; name?: unknown; modules?: unknown } | null
    const login = typeof body?.login === "string" ? body.login.trim().toLowerCase() : ""
    const email = login.includes("@") ? login : USER_NAME.test(login) ? `${login}@kiara.local` : ""
    if (!email || email.length > 254 || !EMAIL.test(email)) {
      return Response.json({ error: "Informe um e-mail válido ou um nome de usuário (letras, números, ponto, hífen)." }, { status: 400 })
    }
    if (isSystemAdminEmail(email)) return Response.json({ error: "Essa conta já é de administrador." }, { status: 400 })
    const password = typeof body?.password === "string" ? body.password : ""
    if (password.length < 6 || password.length > 72) return Response.json({ error: "A senha precisa ter de 6 a 72 caracteres." }, { status: 400 })
    const name = typeof body?.name === "string" ? body.name.trim().slice(0, 80) : ""
    // The administrator chooses the modules of every new account (none chosen = the account sees no module yet).
    if (!Array.isArray(body?.modules) || !body.modules.every(isModuleKey)) return Response.json({ error: "Escolha os módulos da conta." }, { status: 400 })
    const chosen = MODULE_KEYS.filter((key) => (body.modules as unknown[]).includes(key))

    const { data, error } = await createAdminClient().auth.admin.createUser({
      email, password, email_confirm: true, user_metadata: name ? { full_name: name } : {}, app_metadata: { modules: chosen },
    })
    if (error) {
      if (/already|registered|exists/i.test(error.message)) return Response.json({ error: "Já existe uma conta com esse login." }, { status: 409 })
      throw error
    }
    const user: AdminUser = {
      id: data.user.id, email, name: name || "Usuário", provider: "E-mail e senha",
      createdAt: data.user.created_at, lastSignInAt: null, isAdmin: false, blocked: false, modules: chosen,
    }
    const loginHint = email.endsWith("@kiara.local") ? email.slice(0, -"@kiara.local".length) : email
    return Response.json({ ok: true, user, message: `Conta criada. Login: ${loginHint}` })
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) return Response.json({ error: "Sessão expirada." }, { status: 401 })
    if (error instanceof AdministratorRequiredError) return Response.json({ error: "Acesso exclusivo do administrador." }, { status: 403 })
    return Response.json({ error: error instanceof Error ? error.message : "Não foi possível criar a conta." }, { status: 500 })
  }
}
