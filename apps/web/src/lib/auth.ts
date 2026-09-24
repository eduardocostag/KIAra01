import "server-only";
import { createClient } from "@/lib/supabase/server";

export type WorkspaceRole = "admin" | "member";
export type WorkspaceContext = Readonly<{ userId: string; workspaceId: string; role: WorkspaceRole }>;
export class AuthenticationRequiredError extends Error {}

/** The only tenant context application services may trust. Never accept workspaceId from request data. */
export async function requireWorkspace(): Promise<WorkspaceContext> {
  const supabase = await createClient()
  const { data, error } = await supabase.auth.getClaims()
  const userId = typeof data?.claims?.sub === "string" ? data.claims.sub : null
  if (error || !userId) throw new AuthenticationRequiredError("Authentication required")
  return { userId, workspaceId: userId, role: "admin" }
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
