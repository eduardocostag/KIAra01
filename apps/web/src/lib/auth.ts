import "server-only";
import { auth } from "@clerk/nextjs/server";
import { resolveAuthMode } from "./auth-config";

export type WorkspaceRole = "admin" | "member";
export type WorkspaceContext = Readonly<{ mode: "clerk" | "demo"; userId: string; workspaceId: string; role: WorkspaceRole }>;
export class AuthenticationRequiredError extends Error {}
export class ActiveWorkspaceRequiredError extends Error {}

function normalizeRole(role: string | null | undefined): WorkspaceRole {
  return role === "org:admin" || role === "admin" ? "admin" : "member";
}

/** The only tenant context application services may trust. Never accept workspaceId from request data. */
export async function requireWorkspace(): Promise<WorkspaceContext> {
  const mode = resolveAuthMode();
  if (mode === "demo") return { mode, userId: "demo-user", workspaceId: "demo-workspace", role: "admin" };

  const session = await auth();
  if (!session.userId) throw new AuthenticationRequiredError("Authentication required");
  if (!session.orgId) throw new ActiveWorkspaceRequiredError("An active organization is required");
  return { mode, userId: session.userId, workspaceId: session.orgId, role: normalizeRole(session.orgRole) };
}
