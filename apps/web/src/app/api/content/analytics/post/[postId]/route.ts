import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";

const VALID_ID = /^[A-Za-z0-9_-]{1,160}$/;

export async function GET(request: Request, { params }: { params: Promise<{ postId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { postId } = await params;
  if (!VALID_ID.test(postId)) return Response.json({ error: { code: "post_id_invalid", message: "Publicação inválida." } }, { status: 422 });
  const requestedDays = Number(new URL(request.url).searchParams.get("days") || 30);
  const days = Math.max(1, Math.min(Number.isFinite(requestedDays) ? requestedDays : 30, 365));
  try {
    return Response.json(await postizRequest(`/public/v1/analytics/post/${encodeURIComponent(postId)}?date=${days}`), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return postizErrorResponse(error);
  }
}
