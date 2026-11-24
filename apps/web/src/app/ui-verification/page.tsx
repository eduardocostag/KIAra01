import { WhatsAppWebWorkspace } from "@/components/app-shell/whatsapp-web-workspace"
import { WhatsAppInbox, WhatsAppSectionShell } from "@/components/app-shell/whatsapp-inbox"
import { AppShell } from "@/components/app-shell/app-shell"
import { InboxHub } from "@/components/app-shell/inbox-hub"
import { notFound } from "next/navigation"
import { ComingSoon } from "@/components/early-access/coming-soon"
import { LaunchBadge } from "@/components/early-access/launch-badge"
import { ChatWorkspace } from "@/components/chat/chat-workspace"
import ModuleSelectorPage from "@/app/(app)/app/page"
import { ModuleChoice } from "@/components/app-shell/module-choice"
import { MODULES } from "@/lib/modules"
import { LeadsDashboard } from "@/components/app-shell/leads-dashboard"
import { LeadDetail } from "@/components/app-shell/lead-detail"
import { WelcomeTour } from "@/components/app-shell/welcome-tour"
import { PageSkeleton } from "@/components/app-shell/page-skeleton"
import { TodayQueue } from "@/components/app-shell/today-queue"
import { CompanyWorkspace } from "@/components/app-shell/company-workspace"
import { TeamWorkspace, PlanWorkspace } from "@/components/app-shell/team-plan"
import { ResultsPanel } from "@/components/app-shell/results-panel"
import { AutomationWorkspace } from "@/components/automation/automation-workspace"
import { HunterClient } from "@/app/(app)/app/(leads-module)/hunter/hunter-client"
import { previewConversations, previewEntries } from "./leads-fixtures"
import { ApprovalCenter, type ActionRequest } from "@/components/approvals/approval-center"
import { LeadCompanyPanel } from "@/components/app-shell/lead-company-panel"
import "../(app)/app/(leads-module)/leads/[leadId]/lead-detail.css"
// Same stylesheets as the real app layout, so previews match production.
import "@/components/fx/effects.css"
import "../(app)/app/reference-surfaces.css"
import "../(app)/app/orbit-dashboard.css"
import { FxPreview } from "./fx-preview"
import { AdminConsole } from "@/components/app-shell/admin-console"
import { SdrSimulator } from "@/components/app-shell/sdr-simulator"
import { ServiceSetupWorkspace } from "@/components/app-shell/service-setup"
import { EMPTY_SETUP, type Niche } from "@/lib/service-setup"

const previewApprovals: ActionRequest[] = [
  { id: "a1", kind: "whatsapp", title: "Enviar WhatsApp: (51) 99999-0000", payload: { to: "(51) 99999-0000", text: "Olá, Dra. Ana! Vi que a Clínica Sorriso tem ótimas avaliações no Google. Posso mostrar como um site pode trazer ainda mais pacientes?", entrada: "" }, status: "pending", note: null, version: 1, flow_name: "Boas-vindas no WhatsApp", created_at: "2026-11-13T12:10:00Z", decided_at: null },
  { id: "a2", kind: "social.instagram", title: "Post no Instagram", payload: { caption: "Seu paciente procura você no Google antes de marcar. #odontologia #marketingdigital", media: "https://exemplo.com/post.jpg", entrada: "" }, status: "pending", note: null, version: 1, flow_name: "Post semanal no Instagram", created_at: "2026-11-13T10:00:00Z", decided_at: null },
  { id: "a3", kind: "notice", title: "Prioridades de hoje", payload: { text: "1. Ligar para a Clínica Sorriso (nota A).\n2. Retomar proposta com Odonto Prime.\n3. Responder Dental Bianco." }, status: "pending", note: null, version: 1, flow_name: "Resumo diário do CRM", created_at: "2026-11-13T11:00:00Z", decided_at: null },
  { id: "a4", kind: "ads.google", title: "Anúncio Google", payload: { objective: "traffic", daily: 30, days: 7, keywords: "site para clínica" }, status: "pending", note: null, version: 1, flow_name: "Campanha Meta + Google", created_at: "2026-11-13T09:00:00Z", decided_at: null },
]

export default async function Page({ searchParams }: { searchParams: Promise<{ workspace?: string; view?: string }> }) {
  if (process.env.NODE_ENV !== "development") notFound()
  const { workspace, view } = await searchParams
  // Conversation modules own their full-height shell, like in the real routes.
  if (workspace === "chat") return <ChatWorkspace isAdmin />
  if (workspace === "admin") return <AppShell previewModule="/app/leads"><div className="mx-auto w-full max-w-7xl"><AdminConsole initialSnapshot={{ generatedAt: new Date().toISOString(), services: [], auditEvents: [], notices: [], users: [
    { id: "11111111-1111-4111-8111-111111111111", email: "eduardocgonsalves@hotmail.com", name: "Eduardo", provider: "E-mail e senha", createdAt: "2026-09-01T10:00:00Z", lastSignInAt: "2026-11-17T20:00:00Z", isAdmin: true, blocked: false, modules: ["leads", "whatsapp", "chat", "automation"] },
    { id: "22222222-2222-4222-8222-222222222222", email: "kiara01@kiara.local", name: "Kiara01", provider: "E-mail e senha", createdAt: "2026-11-17T21:00:00Z", lastSignInAt: null, isAdmin: false, blocked: false, modules: ["leads", "chat"] },
    { id: "33333333-3333-4333-8333-333333333333", email: "cliente@empresa.com", name: "Ana Julia", provider: "Google", createdAt: "2026-10-02T10:00:00Z", lastSignInAt: "2026-11-10T09:00:00Z", isAdmin: false, blocked: true, modules: [] },
  ] }} /></div></AppShell>
  if (workspace === "leads") return <AppShell previewModule="/app/leads"><LeadsDashboard pipeline={{ entries: previewEntries, available: true }} /></AppShell>
  if (workspace === "lead") return <AppShell previewModule="/app/leads"><LeadDetail entry={previewEntries[0]} /></AppShell>
  if (workspace === "pipeline") return <AppShell previewModule="/app/leads"><div className="space-y-4"><InboxHub entries={previewEntries} prospectError="" initialView="contacts" initialContactId="" /></div></AppShell>
  if (workspace === "modules") return <ModuleSelectorPage />
  if (workspace === "module-choice") {
    // ?view=0..6: the selector with that many modules (beyond the four real ones, sample modules show the grid scaling).
    const extra = [{ key: "voz", label: "KIARA Voz", description: "Atendimento por telefone.", href: "/app/voz" }, { key: "video", label: "KIARA Vídeo", description: "Vídeos narrados.", href: "/app/video" }]
    const items = [...MODULES, ...extra].slice(0, Math.max(0, Math.min(6, Number(view) || 0)))
    return <div className="relative flex min-h-dvh flex-col items-center justify-center bg-[#07060d] p-4 sm:p-8"><ModuleChoice modules={items} /></div>
  }
  if (workspace === "fila") return <AppShell previewModule="/app/leads"><div className="mx-auto w-full max-w-6xl"><TodayQueue entries={previewEntries} /></div></AppShell>
  if (workspace === "empresa") return <AppShell previewModule="/app/leads"><div className="mx-auto w-full max-w-4xl"><CompanyWorkspace /></div></AppShell>
  if (workspace === "equipe") return <AppShell previewModule="/app/leads"><div className="mx-auto w-full max-w-4xl"><TeamWorkspace /></div></AppShell>
  if (workspace === "plano") return <AppShell previewModule="/app/leads"><div className="mx-auto w-full max-w-5xl"><PlanWorkspace /></div></AppShell>
  if (workspace === "resultados") return <AppShell previewModule="/app/leads"><div className="mx-auto w-full max-w-6xl"><ResultsPanel /></div></AppShell>
  if (workspace === "welcome") return <div className="min-h-dvh"><WelcomeTour userId={`preview-${view ?? "x"}`} modules={view === "client" ? ["leads"] : ["leads", "chat"]} /></div>
  if (workspace === "skeleton") return <AppShell previewModule="/app/leads"><PageSkeleton variant={(view as "list" | "board" | "detail" | "inbox" | "cards") ?? "list"} /></AppShell>
  if (workspace === "automation-flow") return <AutomationWorkspace />
  if (workspace === "fx") return <FxPreview view={view} />
  if (workspace === "approvals") return <AppShell><ApprovalCenter preview={previewApprovals} /></AppShell>
  if (workspace === "lead-company") return <div className="kiara-lead-detail p-6"><LeadCompanyPanel leadId="preview" initialCompany={{ cnpj: "11222333000181", cnpj_formatted: "11.222.333/0001-81", legal_name: "CLINICA SORRISO ODONTOLOGIA LTDA", trade_name: "Clínica Sorriso", status: "ATIVA", active: true, opened_at: "2015-03-10", size: "DEMAIS", legal_nature: "Sociedade Empresária Limitada", main_activity: "Atividade odontológica", capital: 50000, city: "PORTO ALEGRE", state: "RS", simples: true, mei: false, partners: [{ name: "ANA SOUZA", role: "Sócio-Administrador" }], source: "brasilapi", cnpj_source: "website", fetched_at: "2026-11-13T12:00:00Z" }} initialFit={{ score: 82, grade: "A", label: "Prioridade alta", has_company_data: true, reasons: [{ points: 18, text: "WhatsApp público encontrado" }, { points: 16, text: "Sem site próprio: oportunidade clara" }, { points: 14, text: "230 avaliações no Google: negócio movimentado" }, { points: 10, text: "Empresa com 11 anos: negócio estabelecido" }, { points: 8, text: "Nota 4.8 no Google: clientes satisfeitos" }, { points: 8, text: "CNPJ ativo na Receita Federal" }] }} /></div>
  if (workspace === "launch-badge") return <div className="grid min-h-dvh place-items-center bg-[#07060d] p-8"><div className="flex w-64 flex-col items-center rounded-3xl border border-white/10 bg-black/40 p-8 text-center"><h2 className="mb-2 text-xl font-semibold">KIARA Chat</h2><p className="mb-8 text-sm text-muted-foreground">Conversa, voz e criação com IA.</p><LaunchBadge /><span className="text-sm">Ver novidade</span></div></div>
  if (workspace === "soon-whatsapp" || workspace === "soon-chat" || workspace === "soon-automation") return <ComingSoon module={workspace.slice(5) as "whatsapp" | "chat" | "automation"} />
  if (workspace === "atendimento") {
    const niches: Niche[] = [
      { id: "odontologia", label: "Odontologia", goal: "schedule", payment_label: "Convênios e formas de pagamento", discover: ["Qual tratamento procura ou o que está incomodando", "Se tem dor ou é urgente", "Convênio ou particular", "Melhor dia e horário"], handoff: "Dor forte ou urgência, pedido de orçamento de tratamento completo, reclamação ou dúvida clínica.", care: "Siga o código de ética odontológico: não anuncie promoções nem descontos e não dê diagnóstico ou indique tratamento pelo WhatsApp; o caminho é a avaliação com o dentista.", examples: [["Avaliação", "R$ 100"], ["Limpeza", "R$ 180"], ["Clareamento", "a partir de R$ 900"]] },
      { id: "imobiliaria", label: "Imobiliária e corretores", goal: "visit", payment_label: "Financiamento, permuta e condições", discover: ["Comprar ou alugar", "Bairro ou região", "Faixa de preço"], handoff: "Pedido de proposta ou negociação.", care: "Valores são referência.", examples: [["Apartamento 2 quartos", "R$ 420 mil"]] },
      ...["Estética e beleza", "Clínica e saúde", "Advocacia", "Contabilidade", "Academia e estúdio", "Oficina e autopeças", "Cursos e escolas", "Serviços para empresas", "Loja e varejo"].map((label, index) => ({ id: `n${index}`, label, goal: "quote" as const, payment_label: "Formas de pagamento", discover: [], handoff: "", care: "", examples: [] as [string, string][] })),
    ]
    const setup = view === "empty" ? EMPTY_SETUP : { ...EMPTY_SETUP, niche: "odontologia", services: [{ name: "Avaliação", price: "R$ 100" }, { name: "Clareamento", price: "a partir de R$ 900" }, { name: "Implante", price: "" }], hours: "Seg. a sex., 8h às 18h" }
    return <WhatsAppSectionShell title="Configurar atendimento" isAdmin><ServiceSetupWorkspace isAdmin preview={{ setup, niches }} /></WhatsAppSectionShell>
  }
  if (workspace === "simulador") return <SdrSimulator />
  if (workspace === "whatsapp") return <WhatsAppInbox conversations={view === "empty" ? [] : previewConversations} canSend isAdmin={view !== "client"} />
  if (workspace === "automation") return <WhatsAppSectionShell title="Automação"><WhatsAppWebWorkspace entries={previewEntries} /></WhatsAppSectionShell>
  const content = workspace === "hunter" ? <HunterClient />
    : workspace === "contacts" ? <InboxHub entries={previewEntries} prospectError="" initialView={view ?? "contacts"} initialContactId="" />
      : <WhatsAppWebWorkspace entries={[]} />
  return <AppShell previewModule={workspace === "hunter" || workspace === "contacts" ? "/app/leads" : undefined}>{content}</AppShell>
}
