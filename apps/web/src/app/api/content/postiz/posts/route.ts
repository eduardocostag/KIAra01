import { postizRequest } from "@/lib/postiz/client";
import { parseCreatePost, postizPayload } from "@/lib/postiz/validation";
import { dateRange, integrations, invalid, noStore, posts, POSTIZ_API, withPostizAdmin } from "../_shared";

export async function GET(request: Request) {
  return withPostizAdmin(async () => Response.json({ posts: await posts(dateRange(request)) }, { headers: noStore }));
}

export async function POST(request: Request) {
  return withPostizAdmin(async () => {
    if (Number(request.headers.get("content-length")) > 100000) invalid("Conteúdo excede o limite permitido.", 413);
    const text = await request.text();
    if (text.length > 100000) invalid("Conteúdo excede o limite permitido.", 413);
    let input;
    try { input = parseCreatePost(JSON.parse(text)); }
    catch (error) { invalid(error instanceof SyntaxError ? "JSON inválido." : error instanceof Error ? error.message : "Conteúdo inválido."); }
    const channel = (await integrations()).find((item) => item.id === input.integrationId);
    if (!channel) invalid("Canal não encontrado na conta Postiz configurada.", 404);
    if (channel.disabled) invalid("Este canal está desativado no Postiz. Reconecte-o antes de publicar.", 409);
    if (channel.identifier !== input.provider || (input.settings.__type !== undefined && input.settings.__type !== channel.identifier)) {
      invalid("O provedor informado não corresponde ao canal selecionado.");
    }
    const result = await postizRequest(`${POSTIZ_API}/posts`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(postizPayload(input)),
    });
    return Response.json(result, { status: 201, headers: noStore });
  });
}
