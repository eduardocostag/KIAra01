import "server-only";
import { kiaraApi } from "@/lib/api/server-client";

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
  let apiKey = process.env.POSTIZ_API_KEY?.trim() || "";
  let configuredUrl = process.env.POSTIZ_API_URL?.trim() || "https://api.postiz.com";
  try {
    const response = await kiaraApi("/v1/integrations/postiz/credentials");
    if (response.ok) {
      const stored = await response.json() as { api_key?: unknown; endpoint_url?: unknown };
      if (typeof stored.api_key === "string" && stored.api_key.trim()) apiKey = stored.api_key.trim();
      if (typeof stored.endpoint_url === "string" && stored.endpoint_url.trim()) configuredUrl = stored.endpoint_url.trim();
    } else if (response.status !== 404 && !apiKey) {
      throw new PostizConfigurationError("Não foi possível acessar a configuração protegida do Postiz.");
    }
  } catch (error) {
    if (!apiKey) {
      if (error instanceof PostizConfigurationError) throw error;
      throw new PostizConfigurationError("A integração Postiz ainda não foi configurada.");
    }
  }
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

function safeMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object") return fallback;
  const value = payload as Record<string, unknown>;
  for (const candidate of [value.message, value.msg, value.error]) {
    if (typeof candidate === "string" && candidate.trim()) return candidate.slice(0, 300);
  }
  return fallback;
}

export async function postizRequest(path: string, init: RequestInit = {}): Promise<unknown> {
  const { apiKey, baseUrl } = await configuration();
  const target = new URL(path.replace(/^\/+/, ""), baseUrl.href.endsWith("/") ? baseUrl : new URL(`${baseUrl.href}/`));
  if (target.origin !== baseUrl.origin) throw new PostizConfigurationError("Rota Postiz inválida.");
  const response = await fetch(target, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    headers: {
      Accept: "application/json",
      Authorization: apiKey,
      ...init.headers,
    },
  });
  const text = await response.text();
  if (text.length > MAX_RESPONSE_BYTES) throw new PostizRequestError("A resposta do Postiz excedeu o limite seguro.", 502, "postiz_response_too_large");
  let payload: unknown = {};
  if (text) {
    try { payload = JSON.parse(text); }
    catch { throw new PostizRequestError("O Postiz respondeu em formato inválido.", 502, "postiz_invalid_response"); }
  }
  if (!response.ok) {
    const code = response.status === 401 ? "postiz_auth_failed" : response.status === 429 ? "postiz_rate_limited" : "postiz_request_failed";
    throw new PostizRequestError(safeMessage(payload, `O Postiz respondeu com HTTP ${response.status}.`), response.status, code);
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
