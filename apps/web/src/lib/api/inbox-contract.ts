export type InboxMessageDTO = Readonly<{ id: string; from: "lead" | "operator"; text: string; time: string; status?: string }>
export type InboxConversationDTO = Readonly<{
  id: string; consumerId: string; channel: string; name: string; handle: string; excerpt: string; time: string;
  unread: number; status: string; score: number; temperature: string; messages: readonly InboxMessageDTO[];
  intent: string; confidence: string; owner: string; qualifiedAt: string | null; facts: readonly string[];
  gaps: readonly string[]; nextAction: string; suggestedDraft: string; automationEnabled: boolean; handoff: boolean;
  savedDraft: Readonly<{ text: string; status: "draft" | "approved" | "invalidated" }> | null;
}>
type ObjectValue = Record<string, unknown>
function object(value: unknown): ObjectValue { if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Conversa inválida."); return value as ObjectValue }
function text(value: unknown, fallback = "") { return typeof value === "string" ? value : fallback }
function time(value: unknown) { const date = new Date(text(value)); return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }).format(date) : "—" }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [] }
export function parseInboxDetail(value: unknown): InboxConversationDTO {
  const item = object(value), consumer = object(item.consumer)
  if (typeof item.id !== "string" || !item.id || !Array.isArray(item.messages)) throw new Error("Conversa incompleta.")
  const channel = text(item.channel, "instagram")
  const messages = item.messages.map((raw): InboxMessageDTO => { const message = object(raw); if (!["inbound", "outbound"].includes(text(message.direction)) || typeof message.id !== "string" || typeof message.text !== "string") throw new Error("Mensagem inválida."); return { id: message.id, from: message.direction === "inbound" ? "lead" : "operator", text: message.text, time: time(message.created_at), status: text(message.status) } })
  const qualification = item.qualification ? object(item.qualification) : {}
  const score = typeof qualification.score === "number" && Number.isFinite(qualification.score) ? Math.max(0, Math.min(100, qualification.score)) : 0
  const drafts = Array.isArray(item.drafts) ? item.drafts : []
  const latest = drafts.length ? object(drafts.at(-1)) : null
  const draftStatus = latest && ["draft", "approved", "invalidated"].includes(text(latest.status)) ? latest.status as "draft" | "approved" | "invalidated" : "draft"
  const facts = strings(qualification.reasons).length ? strings(qualification.reasons) : strings(qualification.facts)
  return { id: item.id, consumerId: text(consumer.id), channel, name: text(consumer.display_name, "Contato"), handle: channel.startsWith("whatsapp") ? text(consumer.phone, "Telefone não informado") : text(consumer.instagram_username) ? `@${text(consumer.instagram_username).replace(/^@/, "")}` : text(consumer.phone, channel), excerpt: messages.at(-1)?.text ?? "Sem mensagens", time: time(item.updated_at), unread: typeof item.unread_count === "number" ? item.unread_count : 0, status: text(item.status, "open"), score, temperature: text(qualification.temperature, "unknown"), messages, intent: text(qualification.intent, qualification.temperature ? "Qualificação comercial" : "Aguardando qualificação"), confidence: typeof qualification.confidence === "number" ? `${Math.round(qualification.confidence * 100)}% de confiança` : "Baseado nos sinais disponíveis", owner: text(item.owner, "Equipe"), qualifiedAt: qualification.created_at ? time(qualification.created_at) : null, facts, gaps: strings(qualification.gaps), nextAction: text(qualification.next_action, text(qualification.recommendation, "Revisar a conversa e definir a próxima ação.")), suggestedDraft: latest ? text(latest.text) : "", savedDraft: latest ? { text: text(latest.text), status: draftStatus } : null, automationEnabled: item.automation_enabled === true, handoff: item.handoff === true }
}
export const channelLabels: Record<string, string> = { whatsapp: "WhatsApp", whatsapp_web: "WhatsApp Web", instagram: "Instagram", chatwoot: "Chatwoot", email: "Email", facebook: "Facebook" }
export const temperatureLabels: Record<string, string> = { cold: "Frio", warm: "Morno", hot: "Quente", unknown: "Não classificado" }
export const deliveryLabels: Record<string, string> = { queued: "Na fila", pending: "Na fila", sending: "Em envio", sent: "Enviado ao canal", confirmed: "Confirmado", unknown: "Envio incerto · revisar", failed: "Falha no envio", cancelled: "Cancelado" }
export function sendOutcome(value: unknown): { accepted: boolean; uncertain: boolean; message: string } {
  const status = value && typeof value === "object" && "status" in value ? value.status : "unknown"
  if (status === "failed" || status === "cancelled") return { accepted: false, uncertain: false, message: "A mensagem não foi enviada. O rascunho foi preservado; revise a conexão do canal." }
  if (status === "unknown" || !["queued", "pending", "sending", "sent", "confirmed"].includes(String(status))) return { accepted: false, uncertain: true, message: "Não foi possível confirmar o resultado. O reenvio está bloqueado para evitar duplicação; confira a conversa no canal." }
  return { accepted: true, uncertain: false, message: status === "sent" || status === "confirmed" ? "Resposta aceita pelo canal. Confira o histórico de entrega." : "Resposta na fila do executor. Aguarde a confirmação no histórico; fila não significa entrega." }
}
