import { postizRequest } from "@/lib/postiz/client";
import { identifier, noStore, POSTIZ_API, withPostizAdmin } from "../../_shared";

export async function DELETE(_request: Request, { params }: { params: Promise<{ postId: string }> }) {
  return withPostizAdmin(async () => {
    const { postId } = await params;
    // Postiz deletes every post in this post's group.
    await postizRequest(`${POSTIZ_API}/posts/${identifier(postId)}`, { method: "DELETE" });
    return new Response(null, { status: 204, headers: noStore });
  });
}
