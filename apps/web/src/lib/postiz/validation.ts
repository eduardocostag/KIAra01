export type CreatePostInput = {
  type: "draft" | "schedule" | "now";
  date: string;
  integrationId: string;
  provider: string;
  content: string;
  media: Array<{ id: string; path: string }>;
  settings: Record<string, unknown>;
};

const IDENTIFIER = /^[A-Za-z0-9_-]{1,160}$/;
const PROVIDER = /^[A-Za-z0-9_-]{1,80}$/;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Payload inválido.");
  return value as Record<string, unknown>;
}

function safeSettings(value: unknown): Record<string, unknown> {
  const settings = object(value ?? {});
  const encoded = JSON.stringify(settings);
  if (encoded.length > 20_000) throw new Error("As configurações do canal excedem o limite permitido.");
  return settings;
}

export function parseCreatePost(value: unknown): CreatePostInput {
  const body = object(value);
  const type = body.type;
  if (!['draft', 'schedule', 'now'].includes(String(type))) throw new Error("Selecione rascunho, agendamento ou publicação imediata.");
  const integrationId = String(body.integrationId ?? "").trim();
  const provider = String(body.provider ?? "").trim();
  const content = String(body.content ?? "").trim();
  if (!IDENTIFIER.test(integrationId)) throw new Error("Canal Postiz inválido.");
  if (!PROVIDER.test(provider)) throw new Error("Provedor Postiz inválido.");
  if (content.length > 10_000) throw new Error("O conteúdo excede 10.000 caracteres.");
  const dateValue = String(body.date ?? "");
  const parsedDate = Date.parse(dateValue);
  if (!Number.isFinite(parsedDate)) throw new Error("Informe uma data válida.");
  if (type === "schedule" && parsedDate < Date.now() - 60_000) throw new Error("O agendamento precisa estar no futuro.");
  const mediaValue = Array.isArray(body.media) ? body.media : [];
  if (mediaValue.length > 20) throw new Error("Use no máximo 20 mídias.");
  const media = mediaValue.map((entry) => {
    const item = object(entry);
    const id = String(item.id ?? "").trim();
    const path = String(item.path ?? "").trim();
    if (!IDENTIFIER.test(id) || !/^https:\/\//i.test(path) || path.length > 2_000) throw new Error("Mídia Postiz inválida.");
    return { id, path };
  });
  if (!content && !media.length) throw new Error("Adicione texto ou mídia ao conteúdo.");
  return {
    type: type as CreatePostInput["type"],
    date: new Date(parsedDate).toISOString(),
    integrationId,
    provider,
    content,
    media,
    settings: safeSettings(body.settings),
  };
}

export function postizPayload(input: CreatePostInput) {
  return {
    type: input.type,
    date: input.date,
    shortLink: false,
    tags: [],
    creationMethod: "API",
    posts: [{
      integration: { id: input.integrationId },
      value: [{ content: input.content, image: input.media }],
      settings: { ...input.settings, __type: input.provider },
    }],
  };
}
