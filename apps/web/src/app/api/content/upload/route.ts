import { requireAccessToken } from "@/lib/auth";
import { requireContentAdmin } from "@/lib/postiz/admin";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4"]);

export async function POST(request: Request) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const incoming = await request.formData();
  const file = incoming.get("file");
  if (!(file instanceof File)) return Response.json({ error: { code: "file_required", message: "Selecione uma mídia." } }, { status: 422 });
  if (!ALLOWED_TYPES.has(file.type) || file.size <= 0 || file.size > MAX_UPLOAD_BYTES) {
    return Response.json({ error: { code: "file_invalid", message: "Use JPG, PNG, WebP, GIF ou MP4 de até 50 MB." } }, { status: 422 });
  }
  const configuredBase = process.env.KIARA_API_URL?.trim();
  if (!configuredBase) return Response.json({ error: { code: "api_not_configured", message: "KIARA_API_URL não está configurada." } }, { status: 503 });
  const target = new URL("v1/social/media", configuredBase.endsWith("/") ? configuredBase : `${configuredBase}/`);
  try {
    const response = await fetch(target, {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
      headers: {
        Authorization: `Bearer ${await requireAccessToken()}`,
        "Content-Type": file.type,
        "X-Kiara-Filename": encodeURIComponent(file.name.slice(-255)),
        "X-Correlation-ID": crypto.randomUUID(),
      },
      body: await file.arrayBuffer(),
    });
    const text = await response.text();
    return new Response(text, { status: response.status, headers: { "Content-Type": response.headers.get("content-type") || "application/json", "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: { code: "social_upload_failed", message: "Não foi possível armazenar a mídia na Kiara." } }, { status: 502 });
  }
}
