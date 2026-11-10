import "server-only";
import { kiaraApi } from "@/lib/api/server-client";
import { postizTransport } from "./transport";

const DEFAULT_TIMEOUT_MS = 30_000;
const MAX_RESPONSE_BYTES = 8_000_000;

export class PostizConfigurationError extends Error {}
export class PostizRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
  }
}

async function configuration() {
  let apiKey = "";
  let configuredUrl = "";
  const response = await kiaraApi("/v1/integrations/postiz/credentials");
  if (!response.ok) throw new PostizConfigurationError("Conecte o Postiz deste workspace em Configurações > Integrações.");
  const stored = await response.json() as { api_key?: unknown; endpoint_url?: unknown };
  if (typeof stored.api_key === "string") apiKey = stored.api_key.trim();
  if (typeof stored.endpoint_url === "string") configuredUrl = stored.endpoint_url.trim();
  if (!apiKey) throw new PostizConfigurationError("A integração Postiz ainda não foi configurada.");
  let baseUrl: URL;
  try {
    baseUrl = new URL(configuredUrl);
  } catch {
    throw new PostizConfigurationError("A URL do Postiz não é válida.");
  }
  const local = ["localhost", "127.0.0.1", "::1"].includes(baseUrl.hostname);
  if (baseUrl.protocol !== "https:" && !(local && baseUrl.protocol === "http:")) {
    throw new PostizConfigurationError("A URL do Postiz deve usar HTTPS fora do ambiente local.");
  }
  return { apiKey, baseUrl };
}

export async function postizRequest(path: string, init: RequestInit = {}): Promise<unknown> {
  const { apiKey, baseUrl } = await configuration();
  const target = new URL(path.replace(/^\/+/, ""), baseUrl.href.endsWith("/") ? baseUrl : new URL(`${baseUrl.href}/`));
  if (target.origin !== baseUrl.origin) throw new PostizConfigurationError("Rota Postiz inválida.");
  const response = await postizTransport(target, init, new Headers({
      Accept: "application/json",
      Authorization: apiKey,
      ...init.headers,
  }), DEFAULT_TIMEOUT_MS);
  const text = await response.text();
  if (text.length > MAX_RESPONSE_BYTES) throw new PostizRequestError("A resposta do Postiz excedeu o limite seguro.", 502, "postiz_response_too_large");
  let payload: unknown = {};
  if (text) {
    try { payload = JSON.parse(text); }
    catch { throw new PostizRequestError("O Postiz respondeu em formato inválido.", 502, "postiz_invalid_response"); }
  }
  if (!response.ok) {
    const code = response.status === 401 ? "postiz_auth_failed" : response.status === 429 ? "postiz_rate_limited" : "postiz_request_failed";
    throw new PostizRequestError(`O Postiz respondeu com HTTP ${response.status}. Revise a conexão e os dados da publicação.`, response.status, code);
  }
  return payload;
}

export function postizErrorResponse(error: unknown) {
  if (error instanceof PostizConfigurationError) {
    return Response.json({ error: { code: "postiz_not_configured", message: error.message } }, { status: 503 });
  }
  if (error instanceof PostizRequestError) {
    const status = error.status >= 400 && error.status < 500 ? error.status : 502;
    return Response.json({ error: { code: error.code, message: error.message } }, { status });
  }
  const timedOut = error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError");
  return Response.json(
    { error: { code: timedOut ? "postiz_timeout" : "postiz_unavailable", message: timedOut ? "O Postiz demorou além do limite de 30 segundos." : "Não foi possível acessar o Postiz." } },
    { status: timedOut ? 504 : 502 },
  );
}
