import { PostizRequestError } from "@/lib/postiz/client";

const providers = new Set(["instagram-standalone", "facebook", "tiktok", "linkedin", "threads", "youtube"]);

export function connectionProvider(payload: unknown): string {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new PostizRequestError("Informe a rede social para conectar.", 422, "postiz_invalid_input");
  }
  const value = payload as Record<string, unknown>;
  if (Object.keys(value).some((key) => key !== "provider") || typeof value.provider !== "string" || !providers.has(value.provider)) {
    throw new PostizRequestError("Selecione uma rede social suportada para conectar.", 422, "postiz_invalid_input");
  }
  return value.provider;
}

export function connectionUrl(payload: unknown): string {
  const candidate = payload && typeof payload === "object" && "url" in payload ? payload.url : null;
  let url: URL | undefined;
  if (typeof candidate === "string") {
    try { url = new URL(candidate); } catch { /* Invalid upstream response. */ }
  }
  if (!url || url.protocol !== "https:" || url.username || url.password) {
    throw new PostizRequestError("O Postiz retornou um endereço de autorização inválido.", 502, "postiz_invalid_response");
  }
  return url.href;
}

export function connectionStatus(payload: unknown): boolean {
  if (!payload || typeof payload !== "object" || !("connected" in payload) || typeof payload.connected !== "boolean") {
    throw new PostizRequestError("O Postiz retornou um estado de conexão inválido.", 502, "postiz_invalid_response");
  }
  return payload.connected;
}
