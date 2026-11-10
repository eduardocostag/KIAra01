import { postizRequest } from "@/lib/postiz/client";
import { connectionStatus } from "@/lib/postiz/connection";
import { noStore, POSTIZ_API, withPostizAdmin } from "../../_shared";

// This checks the API credential, not the individual social channels.
export async function GET() {
  return withPostizAdmin(async () => {
    const result = await postizRequest(`${POSTIZ_API}/is-connected`);
    return Response.json({ connected: connectionStatus(result) }, { headers: noStore });
  });
}
