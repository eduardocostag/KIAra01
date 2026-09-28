import { requireContentAdmin } from "@/lib/postiz/admin";
import { kiaraApi } from "@/lib/api/server-client";

export async function GET() {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  return kiaraApi("/v1/social/dashboard");
}
