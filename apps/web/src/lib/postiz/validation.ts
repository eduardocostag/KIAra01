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
const PROVIDERS = new Set(["tiktok", "instagram", "instagram-standalone", "facebook", "threads", "linkedin", "linkedin-page", "youtube", "bluesky", "mastodon", "telegram", "nostr", "vk"]);

function httpsUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return /^https:\/\//i.test(value) && url.protocol === "https:" && !!url.hostname && !url.username && !url.password;
  } catch { return false; }
}

function validateSettings(settings: Record<string, unknown>, provider: string, draft: boolean) {
  const enumeration = (field: string, values: string[], required = true) => {
    const value = settings[field];
    if (value === undefined && (draft || !required)) return;
    if (typeof value !== "string" || !values.includes(value)) throw new Error(`Configuração ${field} inválida para ${provider}.`);
  };
  if (provider.startsWith("instagram")) enumeration("post_type", ["post", "story"]);
  if (provider === "tiktok") {
    enumeration("content_posting_method", ["DIRECT_POST"]);
    enumeration("privacy_level", ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"]);
    enumeration("autoAddMusic", ["yes", "no"]);
    for (const field of ["duet", "stitch", "comment", "brand_content_toggle", "brand_organic_toggle", "video_made_with_ai"]) {
      if (settings[field] === undefined && (draft || field === "video_made_with_ai")) continue;
      if (typeof settings[field] !== "boolean") throw new Error(`Configuração ${field} deve ser booleana.`);
    }
    if (settings.title !== undefined && (typeof settings.title !== "string" || settings.title.length > 90)) throw new Error("O título do TikTok deve ter até 90 caracteres.");
  }
  if (provider === "youtube") {
    enumeration("type", ["public", "unlisted", "private"]);
    enumeration("selfDeclaredMadeForKids", ["yes", "no"], false);
    if ((!draft || settings.title !== undefined) && (typeof settings.title !== "string" || settings.title.length > 100 || (!draft && settings.title.trim().length < 2))) throw new Error("O título do YouTube deve ter entre 2 e 100 caracteres.");
  }
}

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
  if (!PROVIDERS.has(provider)) throw new Error("Provedor Postiz inválido.");
  if (content.length > 10_000) throw new Error("O conteúdo excede 10.000 caracteres.");
  const dateValue = String(body.date ?? "");
  const parsedDate = Date.parse(dateValue);
  if (!Number.isFinite(parsedDate)) throw new Error("Informe uma data válida.");
  if (type === "schedule" && parsedDate <= Date.now()) throw new Error("O agendamento precisa estar no futuro.");
  if (body.media !== undefined && !Array.isArray(body.media)) throw new Error("Lista de mídias inválida.");
  const mediaValue = Array.isArray(body.media) ? body.media : [];
  if (mediaValue.length > 20) throw new Error("Use no máximo 20 mídias.");
  const media = mediaValue.map((entry) => {
    const item = object(entry);
    const id = String(item.id ?? "").trim();
    const path = String(item.path ?? "").trim();
    if (!IDENTIFIER.test(id) || !httpsUrl(path) || path.length > 2_000) throw new Error("Mídia Postiz inválida.");
    return { id, path };
  });
  const settings = safeSettings(body.settings);
  validateSettings(settings, provider, type === "draft");
  if (type !== "draft" && ["instagram", "instagram-standalone", "tiktok", "youtube"].includes(provider) && !media.length) throw new Error("Adicione uma mídia para publicar nesta rede.");
  if (type !== "draft" && !content && !media.length) throw new Error("Adicione texto ou mídia ao conteúdo.");
  return {
    type: type as CreatePostInput["type"],
    date: new Date(parsedDate).toISOString(),
    integrationId,
    provider,
    content,
    media,
    settings,
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
