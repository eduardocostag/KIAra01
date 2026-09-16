"use client"

import { useEffect, useState, type ReactNode } from "react"
import { Building2, CheckCircle2, Clock3, LoaderCircle, MessageSquareText, Save, ShieldCheck, Sparkles, UserRound } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { salesRequest, type SalesProfile, templateLabels } from "@/lib/api/sales"

type Section = "operation" | "templates" | "cadence"
const sections = {
  operation: { label: "Identidade", description: "Quem fala e o que oferece", icon: Building2 },
  templates: { label: "Mensagens", description: "Textos para cada situação", icon: MessageSquareText },
  cadence: { label: "Cadência", description: "Horários e acompanhamento", icon: Clock3 },
} satisfies Record<Section, { label: string; description: string; icon: typeof Building2 }>

const templateHelp: Record<string, string> = {
  first_contact: "Mensagem inicial para um novo contato.", no_website: "Abordagem para perfis sem site informado.",
  website_opportunity: "Use quando houver uma oportunidade técnica no site.", instagram_opportunity: "Abordagem baseada na presença pública do Instagram.",
  follow_up: "Lembrete breve quando ainda não houve resposta.", reactivation: "Retome uma conversa que ficou parada.",
  objection: "Resposta-base para dúvidas ou resistência.", interest: "Continuação para quem demonstrou interesse.",
}

export function SettingsForm() {
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [section, setSection] = useState<Section>("operation")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => { void salesRequest<SalesProfile>("/api/sales/profile").then(setProfile).catch((error) => setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao carregar." })) }, [])

  async function save() {
    if (!profile) return
    setBusy(true); setMessage(null)
    try {
      const saved = await salesRequest<SalesProfile>("/api/sales/profile", { method: "PUT", body: JSON.stringify(profile) })
      setProfile(saved); setMessage({ ok: true, text: "Alterações salvas neste workspace." })
    } catch (error) { setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao salvar." }) }
    finally { setBusy(false) }
  }

  if (!profile) return <Card className="overflow-hidden"><CardContent className="flex min-h-64 items-center justify-center text-sm text-muted-foreground"><LoaderCircle className="size-5 animate-spin" /><span className="ml-3">Carregando configurações…</span></CardContent></Card>

  const active = sections[section]
  const ActiveIcon = active.icon
  return <div className="space-y-5">
    {message ? <Alert variant={message.ok ? "default" : "destructive"} className={message.ok ? "border-emerald-500/20 bg-emerald-500/5" : undefined}>{message.ok ? <CheckCircle2 /> : <ShieldCheck />}<AlertTitle>{message.ok ? "Configurações atualizadas" : "Não foi possível salvar"}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert> : null}
    <Tabs value={section} onValueChange={(value) => { setSection(value as Section); setMessage(null) }} orientation="vertical" className="grid items-start gap-5 lg:grid-cols-[250px_minmax(0,1fr)]">
      <aside className="lg:sticky lg:top-7"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5"><CardTitle className="text-sm">Áreas de configuração</CardTitle><CardDescription className="text-xs leading-5">Escolha uma seção para editar.</CardDescription></CardHeader><CardContent className="p-2">
        <TabsList className="grid h-auto w-full gap-1 bg-transparent p-0">{(Object.entries(sections) as [Section, typeof sections[Section]][]).map(([value, item]) => { const Icon = item.icon; return <TabsTrigger key={value} value={value} className="h-auto w-full justify-start gap-3 rounded-xl px-3 py-3.5 text-left data-active:bg-primary/12 data-active:text-foreground"><span className="grid size-9 shrink-0 place-items-center rounded-lg border bg-background text-primary"><Icon className="size-4" /></span><span className="min-w-0"><strong className="block text-sm font-semibold">{item.label}</strong><small className="mt-0.5 block truncate text-[11px] font-normal text-muted-foreground">{item.description}</small></span></TabsTrigger> })}</TabsList>
      </CardContent></Card></aside>

      <div className="min-w-0 space-y-4">
        <div className="flex items-start gap-3 px-1"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary"><ActiveIcon className="size-5" /></span><div><h2 className="text-xl font-semibold tracking-tight">{active.label}</h2><p className="mt-1 text-sm text-muted-foreground">{active.description}</p></div></div>

        <TabsContent value="operation"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Dados da sua operação</CardTitle><CardDescription>A Kiara usa estas informações para preparar mensagens coerentes com seu negócio.</CardDescription></CardHeader><CardContent className="grid gap-6 p-5 sm:p-6 md:grid-cols-2">
          <Field id="business-name" label="Nome do negócio" help="Como sua empresa deve ser apresentada."><Input id="business-name" value={profile.business_name} onChange={(e) => setProfile({ ...profile, business_name: e.target.value })} maxLength={160} placeholder="Ex.: Agência Aurora" /></Field>
          <Field id="sender-name" label="Nome do remetente" help="Pessoa que assina as mensagens."><Input id="sender-name" value={profile.sender_name} onChange={(e) => setProfile({ ...profile, sender_name: e.target.value })} maxLength={160} placeholder="Ex.: Eduardo" /></Field>
          <Field id="main-offer" label="Oferta principal" help="Explique o que você vende e qual resultado entrega." wide><Textarea id="main-offer" value={profile.offer} onChange={(e) => setProfile({ ...profile, offer: e.target.value })} className="min-h-32 resize-y" maxLength={4000} placeholder="Ex.: Ajudamos clínicas a gerar oportunidades qualificadas por meio de…" /></Field>
          <Field id="service-tone" label="Tom de atendimento" help="Descreva como a Kiara deve escrever." wide><Input id="service-tone" value={profile.tone} onChange={(e) => setProfile({ ...profile, tone: e.target.value })} maxLength={500} placeholder="Ex.: consultivo, direto, cordial e sem exageros" /></Field>
        </CardContent></Card></TabsContent>

        <TabsContent value="templates"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Biblioteca de mensagens</CardTitle><CardDescription>Personalize os textos usados em cada situação. As variáveis são substituídas no momento da abordagem.</CardDescription></CardHeader><CardContent className="p-5 sm:p-6">
          <div className="mb-6 flex flex-wrap gap-2 rounded-xl border bg-muted/30 p-3" aria-label="Variáveis disponíveis"><span className="mr-1 self-center text-xs text-muted-foreground">Variáveis:</span>{["remetente", "nome", "nicho", "cidade", "oferta"].map((variable) => <code key={variable} className="rounded-md border bg-background px-2 py-1 text-[11px] text-primary">{`{${variable}}`}</code>)}</div>
          <div className="grid gap-4 xl:grid-cols-2">{Object.entries(profile.templates).map(([key, value]) => <Field key={key} id={`template-${key}`} label={templateLabels[key] || key} help={templateHelp[key] || "Modelo personalizado para esta etapa."}><Textarea id={`template-${key}`} value={value} onChange={(e) => setProfile({ ...profile, templates: { ...profile.templates, [key]: e.target.value } })} className="min-h-36 resize-y" maxLength={20000} /></Field>)}</div>
        </CardContent></Card></TabsContent>

        <TabsContent value="cadence"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Janela de relacionamento</CardTitle><CardDescription>Defina quando os contatos podem ser trabalhados e em quanto tempo devem voltar para a fila.</CardDescription></CardHeader><CardContent className="grid gap-6 p-5 sm:p-6 md:grid-cols-3">
          <Field id="follow-up-hours" label="Novo acompanhamento" help="Tempo após a última interação."><div className="relative"><Input id="follow-up-hours" className="pr-16" type="number" min={1} max={720} value={profile.follow_up_hours} onChange={(e) => setProfile({ ...profile, follow_up_hours: Number(e.target.value) })} /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">horas</span></div></Field>
          <Field id="contact-start" label="Início dos contatos" help="Primeiro horário permitido."><Input id="contact-start" type="time" value={profile.contact_start} onChange={(e) => setProfile({ ...profile, contact_start: e.target.value })} /></Field>
          <Field id="contact-end" label="Fim dos contatos" help="Último horário permitido."><Input id="contact-end" type="time" value={profile.contact_end} onChange={(e) => setProfile({ ...profile, contact_end: e.target.value })} /></Field>
          <div className="md:col-span-3 flex gap-3 rounded-xl border border-primary/15 bg-primary/5 p-4 text-sm leading-6 text-muted-foreground"><Sparkles className="mt-0.5 size-4 shrink-0 text-primary" /><p>Esses horários organizam lembretes e próximos passos. A Kiara não envia mensagens automaticamente apenas por causa desta configuração.</p></div>
        </CardContent></Card></TabsContent>

        <div className="sticky bottom-4 z-10 flex flex-col gap-3 rounded-2xl border bg-background/92 p-3 shadow-xl backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3 px-1"><UserRound className="size-4 text-primary" /><p className="text-xs text-muted-foreground">As alterações valem para todo o workspace.</p></div><Button onClick={save} disabled={busy} size="lg" className="min-w-48">{busy ? <LoaderCircle className="animate-spin" /> : <Save />}Salvar alterações</Button></div>
      </div>
    </Tabs>
  </div>
}

function Field({ id, label, help, wide, children }: { id: string; label: string; help: string; wide?: boolean; children: ReactNode }) {
  return <div className={`grid content-start gap-2 rounded-xl border bg-background/35 p-4 ${wide ? "md:col-span-2" : ""}`}><div><Label htmlFor={id} className="text-sm font-semibold">{label}</Label><p id={`${id}-help`} className="mt-1 text-xs leading-5 text-muted-foreground">{help}</p></div>{children}</div>
}
