import { requireContentAdmin } from "@/lib/postiz/admin";
import { postizErrorResponse, PostizRequestError, postizRequest } from "@/lib/postiz/client";

export const POSTIZ_API = "public/v1";
export const noStore = { "Cache-Control": "no-store" };

export function invalid(message: string, status = 422): never {
  throw new PostizRequestError(message, status, "postiz_invalid_input");
}

export async function withPostizAdmin(action: () => Promise<Response>) {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  try { return await action(); }
  catch (error) { return postizErrorResponse(error); }
}

export function identifier(value: string) {
  if (!/^[A-Za-z0-9_-]{1,160}$/.test(value)) invalid("Identificador Postiz inválido.");
  return value;
}

export function dateRange(request: Request) {
  const query = new URL(request.url).searchParams;
  const now = new Date();
  const defaultStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const defaultEnd = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1) - 1);
  const start = new Date(query.get("startDate") ?? defaultStart.toISOString());
  const end = new Date(query.get("endDate") ?? defaultEnd.toISOString());
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end < start) {
    invalid("Informe início e fim válidos para o calendário.");
  }
  if (end.getTime() - start.getTime() > 366 * 86400000) invalid("Consulte no máximo 366 dias por vez.");
  return { startDate: start.toISOString(), endDate: end.toISOString() };
}

export function analyticsDays(request: Request) {
  const days = new URL(request.url).searchParams.get("date") ?? "30";
  if (!/^[0-9]{1,3}$/.test(days) || Number(days) < 1 || Number(days) > 90) {
    invalid("Escolha um período de métricas entre 1 e 90 dias.");
  }
  return String(Number(days));
}

export type Integration = { id: string; identifier: string; disabled?: boolean; [key: string]: unknown };
export async function integrations(): Promise<Integration[]> {
  const result = await postizRequest(`${POSTIZ_API}/integrations`);
  if (!Array.isArray(result) || !result.every((item) => item && typeof item === "object" && typeof item.id === "string" && typeof item.identifier === "string")) {
    throw new PostizRequestError("O Postiz retornou canais em formato incompatível.", 502, "postiz_invalid_response");
  }
  return result;
}

export async function posts(range: { startDate: string; endDate: string }) {
  const result = await postizRequest(`${POSTIZ_API}/posts?${new URLSearchParams(range)}`);
  if (!result || typeof result !== "object" || !("posts" in result) || !Array.isArray(result.posts)) {
    throw new PostizRequestError("O Postiz retornou publicações em formato incompatível.", 502, "postiz_invalid_response");
  }
  return result.posts;
}
