import type { InboxConversationDTO } from "@/lib/api/inbox-contract"
import type { PipelineEntry } from "@/lib/api/pipeline"

const now = Date.now()
const hoursAgo = (hours: number) => new Date(now - hours * 3_600_000).toISOString()

function entry(id: string, name: string, stage: PipelineEntry["stage"], extra: Partial<PipelineEntry> = {}, consumer: Partial<PipelineEntry["consumer"]> = {}): PipelineEntry {
  return {
    id: `entry-${id}`,
    stage,
    next_action: null,
    version: 1,
    updated_at: hoursAgo(Number(id)),
    ...extra,
    consumer: {
      id: `lead-${id}`,
      display_name: name,
      instagram_username: null,
      phone: "(51) 99999-00" + id.padStart(2, "0"),
      source: "google_maps",
      address: "Rua dos Andradas, 1200 · Porto Alegre, RS",
      research_query: "Dentistas em Porto Alegre",
      website_status: "not_listed",
      ...consumer,
    },
  }
}

/** Preview-only CRM rows; never used outside the development harness. */
export const previewEntries: PipelineEntry[] = [
  entry("1", "Clínica Sorriso Vivo", "new", { qualification: { score: 82, temperature: "hot", reasons: ["Sem site informado no Maps", "WhatsApp público"], recommendation: "Ofereça um site com agendamento online." } }, { whatsapp_url: "https://wa.me/5551999990001" }),
  entry("2", "Odonto Centro POA", "new"),
  entry("3", "Dra. Marina Lopes", "contacted", { next_action: "Retornar com proposta", next_action_at: hoursAgo(5) }, { source: "instagram", instagram_username: "dra.marinalopes" }),
  entry("4", "Instituto Dental Moinhos", "qualified", { next_action: "Enviar portfólio" }),
  entry("5", "Sorria Mais Zona Sul", "opportunity", { next_action: "Reunião sexta 10h", next_action_at: hoursAgo(-30) }, { notes: "Prefere contato pela manhã." }),
  entry("6", "Clínica Bem Estar Bucal", "won"),
  entry("7", "Dental Point Cidade Baixa", "lost"),
]

const conversation = (id: string, name: string, phone: string, temperature: string, automationEnabled: boolean, unread: number, messages: [("lead" | "operator"), string, string][]): InboxConversationDTO => ({
  id, consumerId: `lead-${id}`, channel: "whatsapp", name, handle: phone, excerpt: messages.at(-1)?.[1] ?? "Sem mensagens", time: messages.at(-1)?.[2] ?? "—",
  unread, status: "open", score: temperature === "hot" ? 84 : 52, temperature, intent: "Qualificação comercial", confidence: "78% de confiança", owner: "Equipe",
  qualifiedAt: null, facts: ["Pediu valores do plano mensal", "Atende em Porto Alegre"], gaps: [], nextAction: "Enviar proposta com o plano mensal.",
  suggestedDraft: "", savedDraft: null, automationEnabled, handoff: !automationEnabled,
  messages: messages.map(([from, text, time], index) => ({ id: `${id}-${index}`, from, text, time, status: from === "operator" ? "confirmed" : undefined })),
})

/** Preview-only WhatsApp conversations. */
export const previewConversations: InboxConversationDTO[] = [
  conversation("c1", "Clínica Sorriso Vivo", "+55 51 99999-0001", "hot", true, 2, [
    ["lead", "Olá! Vi o anúncio de vocês. Quanto custa o site com agendamento?", "09:12"],
    ["operator", "Olá! O plano com agendamento online custa R$ 189/mês e inclui domínio e suporte. Posso enviar a proposta?", "09:13"],
    ["lead", "Pode sim. Vocês atendem em Porto Alegre?", "09:20"],
    ["lead", "E qual o prazo para ficar pronto?", "09:21"],
  ]),
  conversation("c2", "Odonto Centro POA", "+55 51 99999-0002", "warm", false, 0, [
    ["lead", "Bom dia, gostaria de falar com um atendente.", "Ontem"],
    ["operator", "Claro! Já vou te atender pessoalmente.", "Ontem"],
  ]),
  conversation("c3", "Dra. Marina Lopes", "+55 51 99999-0003", "unknown", true, 0, [["lead", "Obrigada pelas informações!", "Seg"]]),
]
