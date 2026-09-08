import "server-only";
import { auth } from "@clerk/nextjs/server";

export type WorkspaceRole = "admin" | "member";
export type WorkspaceContext = Readonly<{ userId: string; workspaceId: string; role: WorkspaceRole }>;
export class AuthenticationRequiredError extends Error {}
export class ActiveWorkspaceRequiredError extends Error {}

function normalizeRole(role: string | null | undefined): WorkspaceRole {
  return role === "org:admin" || role === "admin" ? "admin" : "member";
}

/** The only tenant context application services may trust. Never accept workspaceId from request data. */
export async function requireWorkspace(): Promise<WorkspaceContext> {
  const session = await auth();
  if (!session.userId) throw new AuthenticationRequiredError("Authentication required");
  if (!session.orgId) throw new ActiveWorkspaceRequiredError("An active organization is required");
  return { userId: session.userId, workspaceId: session.orgId, role: normalizeRole(session.orgRole) };
}
