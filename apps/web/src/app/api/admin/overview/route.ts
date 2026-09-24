import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth"
import { getAdminSnapshot } from "@/lib/admin/snapshot"

export async function GET() {
  try {
    await requireSystemAdmin()
    return Response.json(await getAdminSnapshot(), { headers: { "Cache-Control": "no-store" } })
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) return Response.json({ error: "Sessão expirada." }, { status: 401 })
    if (error instanceof AdministratorRequiredError) return Response.json({ error: "Acesso exclusivo do administrador." }, { status: 403 })
    return Response.json({ error: "Não foi possível atualizar o diagnóstico administrativo." }, { status: 500 })
  }
}
