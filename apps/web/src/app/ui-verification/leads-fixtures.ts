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
