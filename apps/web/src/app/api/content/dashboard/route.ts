import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";

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
    const [integrations, posts] = await Promise.all([
      postizRequest("/public/v1/integrations"),
      postizRequest(`/public/v1/posts${query.size ? `?${query}` : ""}`),
    ]);
    return Response.json({ integrations, posts }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return postizErrorResponse(error);
  }
}
