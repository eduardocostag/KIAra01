import { requireAccessToken } from "@/lib/auth";
import { requireContentAdmin } from "@/lib/postiz/admin";

const VALID_ID = /^[A-Za-z0-9_-]{1,160}$/;

export async function GET(_request: Request, { params }: { params: Promise<{ mediaId: string }> }) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const { mediaId } = await params;
  if (!VALID_ID.test(mediaId)) return Response.json({ error: { code: "media_id_invalid", message: "Mídia inválida." } }, { status: 422 });
  const configuredBase = process.env.KIARA_API_URL?.trim();
  if (!configuredBase) return Response.json({ error: { code: "api_not_configured", message: "KIARA_API_URL não está configurada." } }, { status: 503 });
  const target = new URL(`v1/social/media/${encodeURIComponent(mediaId)}/download`, configuredBase.endsWith("/") ? configuredBase : `${configuredBase}/`);
  try {
    const response = await fetch(target, { cache: "no-store", signal: AbortSignal.timeout(60_000), headers: { Authorization: `Bearer ${await requireAccessToken()}`, "X-Correlation-ID": crypto.randomUUID() } });
    return new Response(response.body, { status: response.status, headers: { "Content-Type": response.headers.get("content-type") || "application/octet-stream", "Content-Disposition": response.headers.get("content-disposition") || "attachment", "Cache-Control": "private, no-store" } });
  } catch {
    return Response.json({ error: { code: "social_media_unavailable", message: "A mídia não está disponível." } }, { status: 502 });
  }
}
