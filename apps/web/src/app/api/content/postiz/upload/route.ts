import { postizRequest } from "@/lib/postiz/client";
import { invalid, noStore, POSTIZ_API, withPostizAdmin } from "../_shared";

const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/quicktime", "video/webm"]);

export async function POST(request: Request) {
  return withPostizAdmin(async () => {
    if (Number(request.headers.get("content-length")) > MAX_UPLOAD_BYTES + 65536) invalid("Use mídia de até 4 MB.", 413);
    let incoming: FormData;
    try { incoming = await request.formData(); }
    catch { invalid("Envie a mídia como formulário multipart."); }
    const file = incoming.get("file");
    if (!(file instanceof File) || !file.size) invalid("Selecione uma mídia.");
    if (file.size > MAX_UPLOAD_BYTES) invalid("Use mídia de até 4 MB.", 413);
    if (!TYPES.has(file.type)) invalid("Use JPG, PNG, WebP, GIF, MP4, MOV ou WebM.");
    const form = new FormData();
    form.append("file", file, file.name.slice(-255));
    const result = await postizRequest(`${POSTIZ_API}/upload`, { method: "POST", body: form });
    return Response.json(result, { status: 201, headers: noStore });
  });
}
