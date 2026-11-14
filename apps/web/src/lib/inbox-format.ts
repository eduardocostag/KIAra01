/** Presentation helpers for the conversation inbox: media placeholders, day separators and list times. */

export type MediaKind = "sticker" | "image" | "video" | "audio" | "document" | "location" | "other"

const MEDIA: Record<string, { kind: MediaKind; label: string }> = {
  "[figurinha]": { kind: "sticker", label: "Figurinha" },
  "[imagem]": { kind: "image", label: "Foto" },
  "[vídeo]": { kind: "video", label: "Vídeo" },
  "[áudio]": { kind: "audio", label: "Áudio" },
  "[documento]": { kind: "document", label: "Documento" },
  "[localização]": { kind: "location", label: "Localização" },
  "[mensagem]": { kind: "other", label: "Mensagem sem texto" },
}

/** "[figurinha]" and friends (how synced media without caption is stored) -> kind + friendly label. */
export function mediaOf(text: string): { kind: MediaKind; label: string } | null {
  return MEDIA[text.trim().toLowerCase()] ?? null
}

const ZONE = "America/Sao_Paulo"
const dayKey = (date: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: ZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(date)
const daysBetween = (from: Date, to: Date) => Math.round((Date.parse(dayKey(to)) - Date.parse(dayKey(from))) / 86_400_000)

function parse(value: string): Date | null {
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? date : null
}

/** Separator between days inside a conversation: Hoje, Ontem, weekday (this week) or "12 de novembro [de 2025]". */
export function dayLabel(value: string, now = new Date()): string {
  const date = parse(value)
  if (!date) return ""
  const days = daysBetween(date, now)
  if (days === 0) return "Hoje"
  if (days === 1) return "Ontem"
  if (days > 1 && days < 7) {
    const weekday = new Intl.DateTimeFormat("pt-BR", { timeZone: ZONE, weekday: "long" }).format(date)
    return weekday.charAt(0).toUpperCase() + weekday.slice(1)
  }
  const sameYear = new Intl.DateTimeFormat("en", { timeZone: ZONE, year: "numeric" }).format(date) === new Intl.DateTimeFormat("en", { timeZone: ZONE, year: "numeric" }).format(now)
  return new Intl.DateTimeFormat("pt-BR", { timeZone: ZONE, day: "numeric", month: "long", ...(sameYear ? {} : { year: "numeric" }) }).format(date)
}

/** True when two timestamps fall on different calendar days (São Paulo time). */
export function differentDay(a: string, b: string): boolean {
  const first = parse(a), second = parse(b)
  return !first || !second || dayKey(first) !== dayKey(second)
}

/** Time shown next to a conversation in the list, like WhatsApp: 14:05, Ontem, terça, 03/11/25. */
export function listTime(value: string, now = new Date()): string {
  const date = parse(value)
  if (!date) return ""
  const days = daysBetween(date, now)
  if (days <= 0) return new Intl.DateTimeFormat("pt-BR", { timeZone: ZONE, hour: "2-digit", minute: "2-digit" }).format(date)
  if (days === 1) return "Ontem"
  if (days < 7) return new Intl.DateTimeFormat("pt-BR", { timeZone: ZONE, weekday: "short" }).format(date).replace(".", "")
  return new Intl.DateTimeFormat("pt-BR", { timeZone: ZONE, day: "2-digit", month: "2-digit", year: "2-digit" }).format(date)
}
