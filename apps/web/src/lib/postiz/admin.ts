import "server-only";
import { AuthenticationRequiredError, requireWorkspace } from "@/lib/auth";

export async function requireContentAdmin(): Promise<Response | null> {
  try {
    await requireWorkspace();
    return null;
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) {
      return Response.json({ error: { code: "authentication_required", message: "Entre novamente na Kiara." } }, { status: 401 });
    }
    throw error;
  }
}
