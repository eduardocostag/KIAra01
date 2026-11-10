import { socialPostPayload } from "@/lib/social/validation";
import { requireContentAdmin } from "@/lib/postiz/admin";
import { kiaraApi } from "@/lib/api/server-client";

const VALID_ID = /^[A-Za-z0-9_-]{1,160}$/;

export async function DELETE(_request: Request, { params }: { params: Promise<{ postId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { postId } = await params;
  if (!VALID_ID.test(postId)) return Response.json({ error: { code: "post_id_invalid", message: "Publicação inválida." } }, { status: 422 });
  return kiaraApi(`/v1/social/posts/${encodeURIComponent(postId)}`, { method: "DELETE" });
}

export async function PUT(request: Request, { params }: { params: Promise<{ postId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { postId } = await params;
  if (!VALID_ID.test(postId)) return Response.json({ error: { message: "Publicação inválida." } }, { status: 422 });
  const version = request.headers.get("If-Match");
  if (!version) return Response.json({ error: { message: "Atualize a lista antes de editar." } }, { status: 428 });
  try {
    const payload = socialPostPayload(await request.json());
    return kiaraApi(`/v1/social/posts/${encodeURIComponent(postId)}`, { method: "PUT", headers: { "If-Match": version }, body: JSON.stringify(payload) });
  } catch (error) {
    return Response.json({ error: { message: error instanceof Error ? error.message : "Payload inválido." } }, { status: 422 });
  }
}
