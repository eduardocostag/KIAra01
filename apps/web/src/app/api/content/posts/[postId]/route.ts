import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";

const VALID_ID = /^[A-Za-z0-9_-]{1,160}$/;

export async function DELETE(_request: Request, { params }: { params: Promise<{ postId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { postId } = await params;
  if (!VALID_ID.test(postId)) return Response.json({ error: { code: "post_id_invalid", message: "Publicação inválida." } }, { status: 422 });
  try {
    return Response.json(await postizRequest(`/public/v1/posts/${encodeURIComponent(postId)}`, { method: "DELETE" }));
  } catch (error) {
    return postizErrorResponse(error);
  }
}
