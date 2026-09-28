import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";

const VALID_ID = /^[A-Za-z0-9_-]{1,160}$/;

export async function GET(request: Request, { params }: { params: Promise<{ integrationId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { integrationId } = await params;
  if (!VALID_ID.test(integrationId)) return Response.json({ error: { code: "integration_id_invalid", message: "Canal inválido." } }, { status: 422 });
  const requestedDays = Number(new URL(request.url).searchParams.get("days") || 30);
  const days = Math.max(1, Math.min(Number.isFinite(requestedDays) ? requestedDays : 30, 365));
  try {
    return Response.json(await postizRequest(`/public/v1/analytics/${encodeURIComponent(integrationId)}?date=${days}`), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return postizErrorResponse(error);
  }
}
