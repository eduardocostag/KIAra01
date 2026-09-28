import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";
import { parseCreatePost, postizPayload } from "@/lib/postiz/validation";

export async function GET(request: Request) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  const incoming = new URL(request.url);
  const query = new URLSearchParams();
  for (const key of ["startDate", "endDate", "integration", "page", "limit"]) {
    const value = incoming.searchParams.get(key);
    if (value && value.length <= 160) query.set(key, value);
  }
  try {
    return Response.json(await postizRequest(`/public/v1/posts${query.size ? `?${query}` : ""}`), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return postizErrorResponse(error);
  }
}

export async function POST(request: Request) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  try {
    const input = parseCreatePost(await request.json());
    return Response.json(await postizRequest("/public/v1/posts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(postizPayload(input)),
    }), { status: 201 });
  } catch (error) {
    if (error instanceof SyntaxError || (error instanceof Error && ["Payload inválido.", "Canal Postiz inválido.", "Provedor Postiz inválido.", "Mídia Postiz inválida."].some((message) => error.message.includes(message)))) {
      return Response.json({ error: { code: "content_invalid", message: error instanceof Error ? error.message : "Payload inválido." } }, { status: 422 });
    }
    if (error instanceof Error && !("status" in error)) {
      return Response.json({ error: { code: "content_invalid", message: error.message } }, { status: 422 });
    }
    return postizErrorResponse(error);
  }
}
