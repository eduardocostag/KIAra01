import { postizRequest } from "@/lib/postiz/client";
import { analyticsDays, identifier, noStore, POSTIZ_API, withPostizAdmin } from "../../../_shared";

export async function GET(request: Request, { params }: { params: Promise<{ integrationId: string }> }) {
  return withPostizAdmin(async () => {
    const { integrationId } = await params;
    const result = await postizRequest(`${POSTIZ_API}/analytics/${identifier(integrationId)}?date=${analyticsDays(request)}`);
    return Response.json(result, { headers: noStore });
  });
}
