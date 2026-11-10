import { postizRequest } from "@/lib/postiz/client";
import { analyticsDays, identifier, noStore, POSTIZ_API, withPostizAdmin } from "../../../_shared";

export async function GET(request: Request, { params }: { params: Promise<{ postId: string }> }) {
  return withPostizAdmin(async () => {
    const { postId } = await params;
    const result = await postizRequest(`${POSTIZ_API}/analytics/post/${identifier(postId)}?date=${analyticsDays(request)}`);
    return Response.json(result, { headers: noStore });
  });
}
