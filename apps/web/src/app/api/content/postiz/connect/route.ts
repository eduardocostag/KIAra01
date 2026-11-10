import { postizRequest } from "@/lib/postiz/client";
import { connectionProvider, connectionUrl } from "@/lib/postiz/connection";
import { invalid, noStore, POSTIZ_API, withPostizAdmin } from "../_shared";

// Additive contract: POST { provider } -> 200 { url }; OAuth stays managed by Postiz.
export async function POST(request: Request) {
  return withPostizAdmin(async () => {
    let payload: unknown;
    try { payload = await request.json(); }
    catch { invalid("Envie um JSON válido para conectar a rede social."); }
    const provider = connectionProvider(payload);
    const result = await postizRequest(`${POSTIZ_API}/social/${provider}`);
    return Response.json({ url: connectionUrl(result) }, { headers: noStore });
  });
}
