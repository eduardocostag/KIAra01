import { kiaraApi } from "@/lib/api/server-client";
import { requireContentAdmin } from "@/lib/postiz/admin";

const VALID_ID = /^[A-Za-z0-9_-]{1,160}$/;

export async function POST(request: Request, { params }: { params: Promise<{ postId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { postId } = await params;
  if (!VALID_ID.test(postId)) return Response.json({ error: { code: "post_id_invalid", message: "Conteúdo inválido." } }, { status: 422 });
  const version = request.headers.get("If-Match");
  if (!version) return Response.json({ error: { code: "precondition_required", message: "Versão do conteúdo ausente." } }, { status: 428 });
  return kiaraApi(`/v1/social/posts/${encodeURIComponent(postId)}/confirm`, { method: "POST", headers: { "If-Match": version }, body: await request.text() });
}
