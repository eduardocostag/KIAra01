import { WhatsAppWebWorkspace } from "@/components/app-shell/whatsapp-web-workspace"
import { WhatsAppInbox, WhatsAppSectionShell } from "@/components/app-shell/whatsapp-inbox"
import { AppShell } from "@/components/app-shell/app-shell"
import { InboxHub } from "@/components/app-shell/inbox-hub"
import { notFound } from "next/navigation"
import { ComingSoon } from "@/components/early-access/coming-soon"
import { LaunchBadge } from "@/components/early-access/launch-badge"
import { ChatWorkspace } from "@/components/chat/chat-workspace"
import { AutomationWorkspace } from "@/components/automation/automation-workspace"
import { HunterClient } from "@/app/(app)/app/(leads-module)/hunter/hunter-client"
import { previewConversations, previewEntries } from "./leads-fixtures"
import { ApprovalCenter, type ActionRequest } from "@/components/approvals/approval-center"
import { LeadCompanyPanel } from "@/components/app-shell/lead-company-panel"
import "../(app)/app/(leads-module)/leads/[leadId]/lead-detail.css"
import { FxPreview } from "./fx-preview"

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
  if (workspace === "automation-flow") return <AutomationWorkspace />
  if (workspace === "fx") return <FxPreview view={view} />
  if (workspace === "approvals") return <AppShell><ApprovalCenter preview={previewApprovals} /></AppShell>
  if (workspace === "lead-company") return <div className="kiara-lead-detail p-6"><LeadCompanyPanel leadId="preview" initialCompany={{ cnpj: "11222333000181", cnpj_formatted: "11.222.333/0001-81", legal_name: "CLINICA SORRISO ODONTOLOGIA LTDA", trade_name: "Clínica Sorriso", status: "ATIVA", active: true, opened_at: "2015-03-10", size: "DEMAIS", legal_nature: "Sociedade Empresária Limitada", main_activity: "Atividade odontológica", capital: 50000, city: "PORTO ALEGRE", state: "RS", simples: true, mei: false, partners: [{ name: "ANA SOUZA", role: "Sócio-Administrador" }], source: "brasilapi", cnpj_source: "website", fetched_at: "2026-11-13T12:00:00Z" }} initialFit={{ score: 82, grade: "A", label: "Prioridade alta", has_company_data: true, reasons: [{ points: 18, text: "WhatsApp público encontrado" }, { points: 16, text: "Sem site próprio: oportunidade clara" }, { points: 14, text: "230 avaliações no Google: negócio movimentado" }, { points: 10, text: "Empresa com 11 anos: negócio estabelecido" }, { points: 8, text: "Nota 4.8 no Google: clientes satisfeitos" }, { points: 8, text: "CNPJ ativo na Receita Federal" }] }} /></div>
  if (workspace === "launch-badge") return <div className="grid min-h-dvh place-items-center bg-[#07060d] p-8"><div className="flex w-64 flex-col items-center rounded-3xl border border-white/10 bg-black/40 p-8 text-center"><h2 className="mb-2 text-xl font-semibold">KIARA Chat</h2><p className="mb-8 text-sm text-muted-foreground">Conversa, voz e criação com IA.</p><LaunchBadge /><span className="text-sm">Ver novidade</span></div></div>
  if (workspace === "soon-whatsapp" || workspace === "soon-chat" || workspace === "soon-automation") return <ComingSoon module={workspace.slice(5) as "whatsapp" | "chat" | "automation"} />
  if (workspace === "whatsapp") return <WhatsAppInbox conversations={view === "empty" ? [] : previewConversations} canSend />
  if (workspace === "automation") return <WhatsAppSectionShell title="Automação"><WhatsAppWebWorkspace entries={previewEntries} /></WhatsAppSectionShell>
  const content = workspace === "hunter" ? <HunterClient />
    : workspace === "contacts" ? <InboxHub entries={previewEntries} prospectError="" initialView={view ?? "contacts"} initialContactId="" />
      : <WhatsAppWebWorkspace entries={[]} />
  return <AppShell previewModule={workspace === "hunter" || workspace === "contacts" ? "/app/leads" : undefined}>{content}</AppShell>
}
