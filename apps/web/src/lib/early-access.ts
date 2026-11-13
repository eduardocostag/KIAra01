/** Modules still in early access: fully usable only by the system administrator until launch. */
export type EarlyAccessModule = "whatsapp" | "chat" | "automation"

/** Launch moment shown in the countdown. Override with NEXT_PUBLIC_KIARA_LAUNCH_AT (ISO 8601). */
export const LAUNCH_AT = process.env.NEXT_PUBLIC_KIARA_LAUNCH_AT || "2026-12-01T09:00:00-03:00"

export const EARLY_ACCESS: Record<EarlyAccessModule, { name: string; href: string; accent: string; headline: string; pitch: string; teasers: string[] }> = {
  whatsapp: {
    name: "KIARA WhatsApp", href: "/app/whatsapp", accent: "#34d399",
    headline: "A Kiara vai atender no seu WhatsApp.",
    pitch: "Ela lê cada conversa, entende o cliente e responde por você, do jeito que você aprovar.",
    teasers: ["Conexão por código QR", "Respostas que você aprova", "CRM atualizado sozinho"],
  },
  chat: {
    name: "KIARA Chat", href: "/app/chat", accent: "#c4a1ff",
    headline: "Converse com a Kiara.",
    pitch: "Uma assistente para pensar, escrever e criar: propostas, sites, painéis e vídeos narrados por ela.",
    teasers: ["Modo conversa por voz", "Sites e dashboards", "Vídeos de apresentação"],
  },
  automation: {
    name: "KIARA Automation", href: "/app/automation", accent: "#facc15",
    headline: "Seu negócio no piloto automático.",
    pitch: "Monte fluxos ligando blocos, sem programar: agenda, mensagens, redes sociais e anúncios.",
    teasers: ["Editor visual de blocos", "Posts e agenda automáticos", "Anúncios com custo previsto"],
  },
}

/** Backend routes of early-access modules; the site proxy only forwards them for the administrator. */
export const EARLY_ACCESS_API_PREFIXES = ["/v1/chat", "/v1/whatsapp-web", "/v1/automation"]
