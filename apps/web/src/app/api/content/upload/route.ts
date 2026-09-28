import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4"]);

export async function POST(request: Request) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  try {
    const incoming = await request.formData();
    const file = incoming.get("file");
    if (!(file instanceof File)) return Response.json({ error: { code: "file_required", message: "Selecione uma mídia." } }, { status: 422 });
    if (!ALLOWED_TYPES.has(file.type) || file.size <= 0 || file.size > MAX_UPLOAD_BYTES) {
      return Response.json({ error: { code: "file_invalid", message: "Use JPG, PNG, WebP, GIF ou MP4 de até 50 MB." } }, { status: 422 });
    }
    const outbound = new FormData();
    outbound.set("file", file, file.name.replace(/[^A-Za-z0-9._-]/g, "_").slice(-120));
    return Response.json(await postizRequest("/public/v1/upload", { method: "POST", body: outbound }));
  } catch (error) {
    return postizErrorResponse(error);
  }
}
