/** Shared by the setup screen (client) and the pages that preview it (server). */
export type Goal = "" | "schedule" | "visit" | "quote" | "sale" | "handoff"
export type ServiceSetup = {
  niche: string; niche_other: string; services: { name: string; price: string }[]; hide_prices: boolean
  hours: string; address: string; payment: string; goal: Goal; goal_detail: string; discover: string[]
  handoff: string; tone: "" | "formal" | "friendly"; emojis: boolean; never_say: string; extra: string
}
export type Niche = { id: string; label: string; goal: Exclude<Goal, "">; discover: string[]; handoff: string; care: string; examples: [string, string][]; payment_label: string }

export const EMPTY_SETUP: ServiceSetup = { niche: "", niche_other: "", services: [], hide_prices: false, hours: "", address: "", payment: "", goal: "", goal_detail: "", discover: [], handoff: "", tone: "", emojis: true, never_say: "", extra: "" }
