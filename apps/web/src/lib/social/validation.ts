export function socialPostPayload(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Payload inválido.");
  const body = value as Record<string, unknown>;
  const type = String(body.type ?? "draft");
  if (!new Set(["draft", "schedule", "now"]).has(type)) throw new Error("Ação de publicação inválida.");
  const integrationId = String(body.integrationId ?? "").trim();
  if (!/^[A-Za-z0-9_-]{1,160}$/.test(integrationId)) throw new Error("Canal inválido.");
  const content = String(body.content ?? "").trim();
  if (content.length > 10_000) throw new Error("O conteúdo excede 10.000 caracteres.");
  const media = Array.isArray(body.media) ? body.media : [];
  const mediaIds = media.map((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) throw new Error("Mídia inválida.");
    const id = String((entry as Record<string, unknown>).id ?? "").trim();
    if (!/^[A-Za-z0-9_-]{1,160}$/.test(id)) throw new Error("Mídia inválida.");
    return id;
  });
  if (!content && !mediaIds.length) throw new Error("Adicione texto ou mídia ao conteúdo.");
  const date = body.date ? new Date(String(body.date)) : null;
  if (type === "schedule" && (!date || Number.isNaN(date.getTime()))) throw new Error("Informe uma data válida.");
  return {
    content,
    channel_ids: [integrationId],
    media_ids: mediaIds,
    action: type === "now" ? "prepare" : type,
    scheduled_at: type === "schedule" ? date!.toISOString() : null,
  };
}
