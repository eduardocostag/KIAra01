import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, postizRequest } from "@/lib/postiz/client";

export async function GET() {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  try {
    return Response.json(await postizRequest("/public/v1/integrations"), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return postizErrorResponse(error);
  }
}
