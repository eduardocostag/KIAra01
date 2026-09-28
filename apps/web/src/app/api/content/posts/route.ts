import { kiaraApi } from "@/lib/api/server-client";
import { requireContentAdmin } from "@/lib/postiz/admin";
import { socialPostPayload } from "@/lib/social/validation";

export async function GET() {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  return kiaraApi("/v1/social/posts");
}

export async function POST(request: Request) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  try {
    const payload = socialPostPayload(await request.json());
    return kiaraApi("/v1/social/posts", { method: "POST", body: JSON.stringify(payload) });
  } catch (error) {
    return Response.json({ error: { code: "content_invalid", message: error instanceof Error ? error.message : "Payload inválido." } }, { status: 422 });
  }
}
