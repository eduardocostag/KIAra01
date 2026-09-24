import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth"

export async function adminGuardResponse() {
  try {
    await requireSystemAdmin()
    return null
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) return Response.json({ error: { message: "Entre novamente na Kiara." } }, { status: 401 })
    if (error instanceof AdministratorRequiredError) return Response.json({ error: { message: "Prévia exclusiva do administrador." } }, { status: 403 })
    throw error
  }
}
