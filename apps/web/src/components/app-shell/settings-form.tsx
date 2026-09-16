"use client"

import { useEffect, useState, type ReactNode } from "react"
import { Building2, CheckCircle2, LoaderCircle, MessageSquareText, Plus, Save, ShieldCheck, Trash2, UserRound } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { salesRequest, type SalesProfile, templateLabels } from "@/lib/api/sales"

type Section = "operation" | "templates"
const sections = {
  operation: { label: "Identidade", description: "Quem fala e o que oferece", icon: Building2 },
  templates: { label: "Mensagens", description: "Textos para cada situação", icon: MessageSquareText },
} satisfies Record<Section, { label: string; description: string; icon: typeof Building2 }>

const templateHelp: Record<string, string> = {
  first_contact: "Mensagem inicial para um novo contato.", no_website: "Abordagem para perfis sem site informado.",
  website_opportunity: "Use quando houver uma oportunidade técnica no site.", instagram_opportunity: "Abordagem baseada na presença pública do Instagram.",
  follow_up: "Lembrete breve quando ainda não houve resposta.", reactivation: "Retome uma conversa que ficou parada.",
  objection: "Resposta-base para dúvidas ou resistência.", interest: "Continuação para quem demonstrou interesse.",
}
const builtInTemplates = new Set(Object.keys(templateHelp))

function customTemplateLabel(key: string) {
  return key.replace(/^custom_/, "").replace(/_/g, " ").replace(/\b\p{L}/gu, (letter) => letter.toUpperCase())
}

export function SettingsForm() {
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [section, setSection] = useState<Section>("operation")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [newMessageOpen, setNewMessageOpen] = useState(false)
  const [newMessageName, setNewMessageName] = useState("")
  const [newMessageBody, setNewMessageBody] = useState("")
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

  function addMessage() {
    if (!profile || !newMessageName.trim() || !newMessageBody.trim()) return
    const slug = newMessageName.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 70) || "mensagem"
    let key = `custom_${slug}`
    let suffix = 2
    while (profile.templates[key]) key = `custom_${slug}_${suffix++}`
    setProfile({ ...profile, templates: { ...profile.templates, [key]: newMessageBody.trim() } })
    setNewMessageName(""); setNewMessageBody(""); setNewMessageOpen(false)
  }

  function removeMessage(key: string) {
    if (!profile || builtInTemplates.has(key)) return
    const templates = { ...profile.templates }
    delete templates[key]
    setProfile({ ...profile, templates })
  }

  if (!profile) return <Card className="overflow-hidden"><CardContent className="flex min-h-64 items-center justify-center text-sm text-muted-foreground"><LoaderCircle className="size-5 animate-spin" /><span className="ml-3">Carregando configurações…</span></CardContent></Card>

  return <div className="space-y-5">
    {message ? <Alert variant={message.ok ? "default" : "destructive"} className={message.ok ? "border-emerald-500/20 bg-emerald-500/5" : undefined}>{message.ok ? <CheckCircle2 /> : <ShieldCheck />}<AlertTitle>{message.ok ? "Configurações atualizadas" : "Não foi possível salvar"}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert> : null}
    <Tabs value={section} onValueChange={(value) => { setSection(value as Section); setMessage(null) }} orientation="vertical" className="grid items-start gap-5 lg:grid-cols-[250px_minmax(0,1fr)]">
      <aside className="lg:sticky lg:top-7"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5"><CardTitle className="text-sm">Áreas de configuração</CardTitle><CardDescription className="text-xs leading-5">Escolha uma seção para editar.</CardDescription></CardHeader><CardContent className="p-2">
        <TabsList className="grid h-auto w-full gap-1 bg-transparent p-0">{(Object.entries(sections) as [Section, typeof sections[Section]][]).map(([value, item]) => { const Icon = item.icon; return <TabsTrigger key={value} value={value} className="h-auto w-full justify-start gap-3 rounded-xl px-3 py-3.5 text-left data-active:bg-primary/12 data-active:text-foreground"><span className="grid size-9 shrink-0 place-items-center rounded-lg border bg-background text-primary"><Icon className="size-4" /></span><span className="min-w-0"><strong className="block text-sm font-semibold">{item.label}</strong><small className="mt-0.5 block truncate text-[11px] font-normal text-muted-foreground">{item.description}</small></span></TabsTrigger> })}</TabsList>
      </CardContent></Card></aside>

      <div className="min-w-0 space-y-4">
        <TabsContent value="operation"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Dados da sua operação</CardTitle><CardDescription>A Kiara usa estas informações para preparar mensagens coerentes com seu negócio.</CardDescription></CardHeader><CardContent className="grid gap-6 p-5 sm:p-6 md:grid-cols-2">
          <Field id="business-name" label="Nome do negócio" help="Como sua empresa deve ser apresentada."><Input id="business-name" value={profile.business_name} onChange={(e) => setProfile({ ...profile, business_name: e.target.value })} maxLength={160} placeholder="Ex.: Agência Aurora" /></Field>
          <Field id="sender-name" label="Nome do remetente" help="Pessoa que assina as mensagens."><Input id="sender-name" value={profile.sender_name} onChange={(e) => setProfile({ ...profile, sender_name: e.target.value })} maxLength={160} placeholder="Ex.: Eduardo" /></Field>
          <Field id="main-offer" label="Oferta principal" help="Explique o que você vende e qual resultado entrega." wide><Textarea id="main-offer" value={profile.offer} onChange={(e) => setProfile({ ...profile, offer: e.target.value })} className="min-h-32 resize-y" maxLength={4000} placeholder="Ex.: Ajudamos clínicas a gerar oportunidades qualificadas por meio de…" /></Field>
          <Field id="service-tone" label="Tom de atendimento" help="Descreva como a Kiara deve escrever." wide><Input id="service-tone" value={profile.tone} onChange={(e) => setProfile({ ...profile, tone: e.target.value })} maxLength={500} placeholder="Ex.: consultivo, direto, cordial e sem exageros" /></Field>
        </CardContent></Card></TabsContent>

        <TabsContent value="templates"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Biblioteca de mensagens</CardTitle><CardDescription className="mt-1">Personalize os textos usados em cada situação. As variáveis são substituídas no momento da abordagem.</CardDescription></div><Button type="button" onClick={() => setNewMessageOpen(true)} className="shrink-0"><Plus />Nova mensagem</Button></div></CardHeader><CardContent className="p-5 sm:p-6">
          <div className="mb-6 flex flex-wrap gap-2 rounded-xl border bg-muted/30 p-3" aria-label="Variáveis disponíveis"><span className="mr-1 self-center text-xs text-muted-foreground">Variáveis:</span>{["remetente", "nome", "nicho", "cidade", "oferta"].map((variable) => <code key={variable} className="rounded-md border bg-background px-2 py-1 text-[11px] text-primary">{`{${variable}}`}</code>)}</div>
          <div className="grid gap-4 xl:grid-cols-2">{Object.entries(profile.templates).map(([key, value]) => <Field key={key} id={`template-${key}`} label={templateLabels[key] || customTemplateLabel(key)} help={templateHelp[key] || "Modelo personalizado criado por você."} action={!builtInTemplates.has(key) ? <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground hover:text-destructive" onClick={() => removeMessage(key)} aria-label={`Remover ${customTemplateLabel(key)}`}><Trash2 className="size-4" /></Button> : null}><Textarea id={`template-${key}`} value={value} onChange={(e) => setProfile({ ...profile, templates: { ...profile.templates, [key]: e.target.value } })} className="min-h-36 resize-y" maxLength={20000} /></Field>)}</div>
        </CardContent></Card></TabsContent>

        <div className="sticky bottom-4 z-10 flex flex-col gap-3 rounded-2xl border bg-background/92 p-3 shadow-xl backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3 px-1"><UserRound className="size-4 text-primary" /><p className="text-xs text-muted-foreground">As alterações valem para todo o workspace.</p></div><Button onClick={save} disabled={busy} size="lg" className="min-w-48">{busy ? <LoaderCircle className="animate-spin" /> : <Save />}Salvar alterações</Button></div>
      </div>
    </Tabs>
    <Dialog open={newMessageOpen} onOpenChange={setNewMessageOpen}>
      <DialogContent className="sm:max-w-xl"><DialogHeader><DialogTitle>Adicionar nova mensagem</DialogTitle><DialogDescription>Crie um modelo para uma situação específica. Ele ficará disponível ao preparar uma abordagem.</DialogDescription></DialogHeader><div className="grid gap-5 py-2"><div className="grid gap-2"><Label htmlFor="new-message-name">Nome do modelo</Label><Input id="new-message-name" value={newMessageName} onChange={(event) => setNewMessageName(event.target.value)} maxLength={70} placeholder="Ex.: Retorno após orçamento" autoFocus /></div><div className="grid gap-2"><Label htmlFor="new-message-body">Mensagem</Label><Textarea id="new-message-body" value={newMessageBody} onChange={(event) => setNewMessageBody(event.target.value)} className="min-h-40 resize-y" maxLength={20000} placeholder="Escreva a mensagem e use variáveis como {nome} e {oferta}." /><p className="text-xs text-muted-foreground">Variáveis disponíveis: {'{remetente}'}, {'{nome}'}, {'{nicho}'}, {'{cidade}'} e {'{oferta}'}.</p></div></div><DialogFooter><Button type="button" variant="outline" onClick={() => setNewMessageOpen(false)}>Cancelar</Button><Button type="button" onClick={addMessage} disabled={!newMessageName.trim() || !newMessageBody.trim() || Object.keys(profile.templates).length >= 30}><Plus />Adicionar à biblioteca</Button></DialogFooter></DialogContent>
    </Dialog>
  </div>
}

function Field({ id, label, help, wide, action, children }: { id: string; label: string; help: string; wide?: boolean; action?: ReactNode; children: ReactNode }) {
  return <div className={`grid content-start gap-2 rounded-xl border bg-background/35 p-4 ${wide ? "md:col-span-2" : ""}`}><div className="flex items-start justify-between gap-3"><div><Label htmlFor={id} className="text-sm font-semibold">{label}</Label><p id={`${id}-help`} className="mt-1 text-xs leading-5 text-muted-foreground">{help}</p></div>{action}</div>{children}</div>
}
