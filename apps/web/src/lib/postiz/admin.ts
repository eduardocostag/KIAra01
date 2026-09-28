import "server-only";
import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth";

export async function requireContentAdmin(): Promise<Response | null> {
  try {
    await requireSystemAdmin();
    return null;
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) {
      return Response.json({ error: { code: "authentication_required", message: "Entre novamente na Kiara." } }, { status: 401 });
    }
    if (error instanceof AdministratorRequiredError) {
      return Response.json({ error: { code: "administrator_required", message: "Conteúdo está em construção para este usuário." } }, { status: 403 });
    }
    throw error;
  }
}
