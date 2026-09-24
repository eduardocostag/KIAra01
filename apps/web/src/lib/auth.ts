import "server-only";
import { createClient } from "@/lib/supabase/server";

export type WorkspaceRole = "admin" | "member";
export const SYSTEM_ADMIN_EMAIL = "admin@kiara.local";
export type WorkspaceContext = Readonly<{
  userId: string;
  workspaceId: string;
  role: WorkspaceRole;
  email: string | null;
  isSystemAdmin: boolean;
}>;
export class AuthenticationRequiredError extends Error {}
export class AdministratorRequiredError extends Error {}

/** The only tenant context application services may trust. Never accept workspaceId from request data. */
export async function requireWorkspace(): Promise<WorkspaceContext> {
  const supabase = await createClient()
  const { data, error } = await supabase.auth.getClaims()
  const userId = typeof data?.claims?.sub === "string" ? data.claims.sub : null
  if (error || !userId) throw new AuthenticationRequiredError("Authentication required")
  const email = typeof data?.claims?.email === "string" ? data.claims.email.trim().toLowerCase() : null
  const isSystemAdmin = email === SYSTEM_ADMIN_EMAIL
  return { userId, workspaceId: userId, role: isSystemAdmin ? "admin" : "member", email, isSystemAdmin }
}

export async function requireSystemAdmin(): Promise<WorkspaceContext> {
  const workspace = await requireWorkspace()
  if (!workspace.isSystemAdmin) throw new AdministratorRequiredError("Administrator access required")
  return workspace
}

export async function requireAccessToken(): Promise<string> {
  const supabase = await createClient()
  const { data: claims, error: claimsError } = await supabase.auth.getClaims()
  const { data: session, error: sessionError } = await supabase.auth.getSession()
  if (claimsError || sessionError || !claims?.claims?.sub || !session.session?.access_token) {
    throw new AuthenticationRequiredError("Authentication required")
  }
  return session.session.access_token
}
