"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { Bot, Loader2, Megaphone, ScanSearch, ShieldCheck, Trash2, UserPlus, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { leadDisplayName, normalizeWhatsAppPhone, type PipelineEntry } from "@/lib/api/pipeline"
import { connectWhatsAppWeb, whatsappWebRequest as request, type WhatsAppAnalysisJob as AnalysisJob, type WhatsAppConfig as Config, type WhatsAppContact as Contact, type WhatsAppEvents as Events } from "@/lib/whatsapp-web-client"
import { cn } from "@/lib/utils"

const activityLabels: Record<string, string> = {
  inbound: "Mensagem recebida", outbound_observed: "Mensagem enviada", reply: "Resposta automática",
  reply_handoff: "Passou para humano", followup: "Follow-up", outreach: "Primeira abordagem", optout: "Pediu para parar",
  handoff: "Atendimento humano", resume: "Retomada", error: "Erro", recorded: "Registrado", pending: "Na fila",
  sending: "Enviando", sent: "Enviado", confirmed: "Confirmado", uncertain: "Envio incerto · revisar",
  cancelled: "Cancelado", paused: "Pausado",
}

function dateLabel(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" })
}

function Section({ icon: Icon, title, description, children }: { icon: typeof Bot; title: string; description: string; children: ReactNode }) {
  return <section className="rounded-2xl border bg-card p-5">
    <header className="mb-4 flex items-start gap-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary"><Icon className="size-4" aria-hidden="true" /></span>
      <div><h2 className="font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
    </header>
    <div className="space-y-4">{children}</div>
  </section>
}

function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (value: boolean) => void; label: string; hint?: string }) {
  return <label className="flex cursor-pointer items-start gap-3">
    <input type="checkbox" className="mt-1 size-4 accent-[var(--primary)]" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    <span><span className="text-sm font-medium">{label}</span>{hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}</span>
  </label>
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return <div className="space-y-1.5"><label htmlFor={id} className="text-sm font-medium">{label}</label>{children}{hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}</div>
}

/** Kiara on WhatsApp Web: identify/understand conversations, reply, prospect and follow up — only for authorized contacts. */
export function WhatsAppWebWorkspace({ entries }: { entries: PipelineEntry[] }) {
  const router = useRouter()
  const [config, setConfig] = useState<Config | null>(null)
  const [savedEnabled, setSavedEnabled] = useState(false)
  const [events, setEvents] = useState<Events | null>(null)
  const [configError, setConfigError] = useState("")
  const [formError, setFormError] = useState("")
  const [formNotice, setFormNotice] = useState("")
  const [analysisError, setAnalysisError] = useState("")
  const [analysisNotice, setAnalysisNotice] = useState("")
  const [saving, setSaving] = useState(false)
  const [phone, setPhone] = useState("")
  const [name, setName] = useState("")
  const [leadSearch, setLeadSearch] = useState("")
  const [analysis, setAnalysis] = useState<AnalysisJob | null>(null)
  const [analysisStarting, setAnalysisStarting] = useState(false)
  const extensionRequestIdRef = useRef("")
  const analysisId = analysis?.id
  const analysisStatus = analysis?.status

  useEffect(() => {
    function handleExtensionMessage(event: MessageEvent) {
      if (event.source !== window || event.origin !== window.location.origin) return
      const message = event.data
      if (message?.source !== "kiara-whatsapp-extension" || message.type !== "analysis-status" || message.jobId !== extensionRequestIdRef.current) return
      if (message.error) { setAnalysisNotice(""); setAnalysisError(message.error) }
      else { setAnalysisError(""); setAnalysisNotice("Conversas recebidas. A Kiara está entendendo cada contato…") }
    }
    window.addEventListener("message", handleExtensionMessage)
    return () => window.removeEventListener("message", handleExtensionMessage)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void request<Config>("config", { signal: controller.signal }).then((value) => { setConfig(value); setSavedEnabled(value.enabled) }).catch((reason) => { if (!controller.signal.aborted) setConfigError(reason instanceof Error ? reason.message : "Não foi possível carregar a configuração.") })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!analysisId || analysisStatus === "completed" || analysisStatus === "failed") return
    const jobId = analysisId
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refreshAnalysis() {
      try {
        const job = await request<AnalysisJob>(`analysis/${encodeURIComponent(jobId)}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        setAnalysis(job); setAnalysisError("")
        if (job.status === "completed" && job.result) {
          setAnalysisNotice(`Pronto: ${job.result.imported ?? 0} contatos novos no CRM, ${job.result.duplicates ?? 0} atualizados, ${job.result.skipped ?? 0} conversas ignoradas.`)
          router.refresh()
        } else if (job.status === "failed") {
          setAnalysisNotice(""); setAnalysisError(job.result?.error ?? "Não foi possível concluir a análise.")
        } else timer = setTimeout(() => void refreshAnalysis(), 3000)
      } catch (reason) {
        if (!controller.signal.aborted) { setAnalysisError(reason instanceof Error ? reason.message : "Não foi possível consultar a análise."); timer = setTimeout(() => void refreshAnalysis(), 5000) }
      }
    }
    void refreshAnalysis()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [analysisId, analysisStatus, router])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      try { const value = await request<Events>("events", { signal: controller.signal }); if (!controller.signal.aborted) setEvents(value) }
      catch { /* Status stays "não verificado"; the next poll retries. */ }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => void refresh(), 10000) }
    }
    void refresh()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])

  function update(values: Partial<Config>) { setConfig((current) => current ? { ...current, ...values } : current); setFormNotice("") }
  // Any change to who is authorized switches the operation off until it is confirmed again.
  const deauthorize = { enabled: false, pilot_consent_confirmed: false }
  function updateContact(index: number, values: Partial<Contact>) {
    if (!config) return
    const contacts = config.contacts.map((contact, position) => ({
      ...contact,
      ...(values.enabled === true && config.pilot_mode ? { enabled: position === index } : {}),
      ...(position === index ? values : {}),
    }))
    update({ contacts, ...(values.enabled !== undefined ? deauthorize : {}) })
  }
  function addContact(normalized: string, contactName: string) {
    if (!config) return
    const existing = config.contacts.find((contact) => contact.phone === normalized)
    const contacts = existing
      ? config.contacts.map((contact) => ({ ...contact, enabled: contact.phone === normalized || (!config.pilot_mode && contact.enabled), handoff: contact.phone === normalized ? false : contact.handoff }))
      : [...config.contacts.map((contact) => ({ ...contact, enabled: config.pilot_mode ? false : contact.enabled })), { phone: normalized, name: contactName, enabled: true, handoff: false }]
    update({ contacts, ...deauthorize })
    setFormError(""); setFormNotice("Contato adicionado. Revise a ativação e salve.")
  }
  function addManual() {
    const normalized = normalizeWhatsAppPhone(phone)
    if (!normalized) { setFormError("Informe o telefone com DDD, por exemplo (11) 99999-9999. Para outro país, comece com +."); return }
    addContact(normalized, name.trim() || normalized)
    setPhone(""); setName("")
  }
  function addLead(entry: PipelineEntry) {
    const normalized = normalizeWhatsAppPhone(entry.consumer.phone)
    if (!normalized) { setFormError("Esse lead não tem telefone válido com DDD. Complete no CRM."); return }
    addContact(normalized, leadDisplayName(entry.consumer))
    setLeadSearch("")
  }
  const search = leadSearch.trim().toLocaleLowerCase("pt-BR")
  const matchingLeads = search ? entries.filter((entry) => !["won", "lost"].includes(entry.stage) && normalizeWhatsAppPhone(entry.consumer.phone) !== null
    && `${leadDisplayName(entry.consumer)} ${entry.consumer.phone}`.toLocaleLowerCase("pt-BR").includes(search)).slice(0, 8) : []

  async function startAnalysis() {
    setAnalysisStarting(true); setAnalysisError(""); setAnalysisNotice("Conectando ao WhatsApp Web…")
    try {
      await connectWhatsAppWeb()
      const job = await request<AnalysisJob>("analysis", { method: "POST", body: JSON.stringify({ limit: 30 }) })
      setAnalysis(job)
      extensionRequestIdRef.current = job.id
      window.postMessage({ source: "kiara-app", type: "whatsapp-analysis", jobId: job.id, limit: 30 }, window.location.origin)
      setAnalysisNotice("Lendo as conversas recentes…")
    } catch (reason) {
      setAnalysisNotice(""); setAnalysisError(reason instanceof Error ? reason.message : "Não foi possível iniciar a análise.")
    } finally { setAnalysisStarting(false) }
  }

  async function save(pause = false) {
    if (!config) return
    if (!pause && config.enabled && (!config.pilot_consent_confirmed || !config.contacts.some((contact) => contact.enabled && !contact.handoff))) { setFormError("Para ativar, habilite ao menos um contato e confirme a autorização."); return }
    if (!pause && config.enabled && !config.ai_context.trim()) { setFormError("Para ativar, descreva o que a Kiara pode dizer sobre sua empresa."); return }
    if (!pause && (!Number.isInteger(config.followup_hours) || config.followup_hours < 1 || config.followup_hours > 720 || !config.contact_start || !config.contact_end || config.contact_start >= config.contact_end)) { setFormError("Use um follow-up de 1 a 720 horas e um horário de início anterior ao fim."); return }
    setSaving(true); setFormError(""); setFormNotice("")
    try {
      const source = pause ? await request<Config>("config") : config
      const value = await request<Config>("config", { method: "PUT", body: JSON.stringify({ ...source, enabled: pause ? false : source.enabled }) })
      setConfig(value); setSavedEnabled(value.enabled)
      setFormNotice(value.enabled ? "Kiara ativa no WhatsApp, dentro dos contatos, horários e limites definidos." : "Kiara pausada no WhatsApp. Nada será enviado automaticamente.")
    } catch (reason) { setFormError(reason instanceof Error ? reason.message : "Falha ao salvar.") }
    finally { setSaving(false) }
  }

  const analysisBusy = analysisStarting || analysis?.status === "queued" || analysis?.status === "running"
  const online = Boolean(events?.online)
  const activity = events?.items.filter((event) => event.kind !== "heartbeat") ?? []
  const enabledCount = config?.contacts.filter((contact) => contact.enabled && !contact.handoff).length ?? 0

  return <div className="space-y-5">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Kiara no WhatsApp</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Defina o que a Kiara faz no seu WhatsApp. Por enquanto, a execução automática roda pelo executor do WhatsApp Web; com a conexão por QR Code, ela passa a valer quando o executor do OpenWA estiver ligado ao site.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1"><span className={cn("size-1.5 rounded-full", online ? "bg-emerald-400" : "bg-muted-foreground")} aria-hidden="true" />{events ? online ? "Executor conectado" : "Executor desconectado" : "Verificando…"}</span>
        <span className={cn("rounded-full border px-2.5 py-1", savedEnabled ? "border-emerald-400/40 text-emerald-400" : "text-muted-foreground")}>{config ? savedEnabled ? "Kiara ativa" : "Kiara pausada" : "—"}</span>
        {savedEnabled ? <Button type="button" size="sm" variant="outline" onClick={() => void save(true)} disabled={saving}>{saving ? "Pausando…" : "Pausar"}</Button> : null}
      </div>
    </header>

    <Section icon={ScanSearch} title="Identificar e entender" description="A Kiara lê até 30 conversas recentes, identifica quem é cada contato e registra no CRM a etapa, um resumo e a próxima ação. Analisar não envia mensagens.">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" onClick={() => void startAnalysis()} disabled={analysisBusy}>{analysisBusy ? <Loader2 className="animate-spin" /> : <ScanSearch />}{analysisBusy ? "Analisando…" : "Analisar conversas"}</Button>
        {analysisError ? <p role="alert" className="text-sm text-destructive">{analysisError}</p> : analysisNotice ? <p role="status" className="text-sm text-muted-foreground">{analysisNotice}</p> : null}
      </div>
    </Section>

    {!config ? <p className="rounded-2xl border p-5 text-sm text-muted-foreground">{configError || "Carregando configuração…"}</p> : <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); void save() }}>
      <fieldset disabled={saving} className="min-w-0 space-y-5 disabled:opacity-60">
        <legend className="sr-only">Configuração da Kiara no WhatsApp</legend>

        <Section icon={Bot} title="Responder" description="A Kiara responde quem escreve, usando só as informações que você aprovar. Sem informação suficiente, ela passa para um humano.">
          <Toggle checked={config.auto_reply_enabled ?? true} onChange={(value) => update({ auto_reply_enabled: value })} label="Responder mensagens com IA" />
          <Field id="wa-ai-context" label="O que a Kiara pode dizer sobre sua empresa" hint="Serviços, preços aprovados, horários e limites. Não inclua senhas nem dados de clientes.">
            <Textarea id="wa-ai-context" maxLength={6000} value={config.ai_context} onChange={(event) => update({ ai_context: event.target.value })} className="min-h-28" placeholder="Ex.: Criamos sites para clínicas. Plano mensal a partir de R$ 189. Atendemos de seg. a sex., 9h às 18h." />
          </Field>
          <Field id="wa-reply" label="Mensagem ao passar para um humano" hint="Use {name} para o nome do contato.">
            <Textarea id="wa-reply" maxLength={4000} value={config.reply_template} onChange={(event) => update({ reply_template: event.target.value })} className="min-h-20" />
          </Field>
        </Section>

        <Section icon={Megaphone} title="Prospectar" description="Primeira abordagem e follow-up para contatos autorizados. Uma abordagem por contato, sempre dentro do horário e do limite diário.">
          <Toggle checked={config.initial_outreach_enabled ?? false} onChange={(value) => update({ initial_outreach_enabled: value })} label="Enviar primeira mensagem a contatos sem conversa" />
          <Field id="wa-outreach" label="Mensagem de abordagem" hint="Use {name} para o nome do contato.">
            <Textarea id="wa-outreach" maxLength={4000} value={config.outreach_template ?? ""} onChange={(event) => update({ outreach_template: event.target.value })} className="min-h-20" placeholder="Olá {name}, tudo bem? …" />
          </Field>
          <Toggle checked={config.followup_enabled ?? false} onChange={(value) => update({ followup_enabled: value })} label="Fazer follow-up quando o contato não responder" />
          <div className="grid gap-4 sm:grid-cols-[160px_1fr]">
            <Field id="wa-followup" label="Após (horas)"><Input id="wa-followup" type="number" min={1} max={720} value={config.followup_hours} onChange={(event) => update({ followup_hours: Number(event.target.value) })} /></Field>
            <Field id="wa-followup-text" label="Mensagem de follow-up"><Textarea id="wa-followup-text" maxLength={4000} value={config.followup_template} onChange={(event) => update({ followup_template: event.target.value })} className="min-h-20" /></Field>
          </div>
        </Section>

        <Section icon={Users} title="Contatos autorizados" description="A Kiara só responde e prospecta os contatos habilitados aqui. Pedidos para parar e atendimento humano pausam a IA no contato.">
          <Field id="wa-lead-search" label="Adicionar do CRM">
            <Input id="wa-lead-search" value={leadSearch} maxLength={200} onChange={(event) => setLeadSearch(event.target.value)} placeholder="Buscar lead por nome ou telefone" />
          </Field>
          {search ? matchingLeads.length ? <ul className="divide-y rounded-xl border">{matchingLeads.map((entry) => <li key={entry.id} className="flex items-center gap-3 px-3 py-2"><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{leadDisplayName(entry.consumer)}</p><p className="text-xs text-muted-foreground">{entry.consumer.phone}</p></div><Button type="button" size="sm" variant="outline" onClick={() => addLead(entry)}><UserPlus />Adicionar</Button></li>)}</ul> : <p className="text-sm text-muted-foreground">Nenhum lead com telefone válido nessa busca.</p> : null}
          <details className="rounded-xl border px-3 py-2"><summary className="cursor-pointer text-sm">Adicionar manualmente</summary>
            <div className="mt-3 grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <Field id="wa-name" label="Nome"><Input id="wa-name" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} /></Field>
              <Field id="wa-phone" label="Telefone com DDD"><Input id="wa-phone" type="tel" placeholder="(11) 99999-9999" value={phone} onChange={(event) => setPhone(event.target.value)} /></Field>
              <Button type="button" variant="outline" onClick={addManual}>Adicionar</Button>
            </div>
          </details>
          {config.contacts.length ? <ul className="divide-y rounded-xl border">{config.contacts.map((contact, index) => <li key={contact.phone} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5">
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{contact.name}</p><p className="text-xs text-muted-foreground">+{contact.phone}</p></div>
            <label className="flex items-center gap-2 text-sm"><input type={config.pilot_mode ? "radio" : "checkbox"} name="wa-pilot-contact" checked={contact.enabled} onChange={() => updateContact(index, { enabled: !contact.enabled })} aria-label={`Habilitar ${contact.name}`} />Habilitado</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={contact.handoff} onChange={(event) => updateContact(index, { handoff: event.target.checked })} aria-label={`Atendimento humano para ${contact.name}`} />Humano</label>
            <Button type="button" variant="ghost" size="icon" className="size-8" aria-label={`Remover ${contact.name}`} onClick={() => update({ ...deauthorize, contacts: config.contacts.filter((_, position) => position !== index) })}><Trash2 /></Button>
          </li>)}</ul> : <p className="text-sm text-muted-foreground">Nenhum contato autorizado ainda.</p>}
        </Section>

        <Section icon={ShieldCheck} title="Limites e ativação" description="Horários, limite diário e a confirmação de que os contatos autorizaram receber mensagens.">
          <div className="grid gap-4 sm:grid-cols-3">
            <Field id="wa-daily-limit" label="Envios por dia"><Input id="wa-daily-limit" type="number" min={1} max={200} value={config.daily_limit ?? 50} onChange={(event) => update({ daily_limit: Number(event.target.value) })} /></Field>
            <Field id="wa-start" label="Início (horário de Brasília)"><Input id="wa-start" type="time" value={config.contact_start} onChange={(event) => update({ contact_start: event.target.value })} /></Field>
            <Field id="wa-end" label="Fim (horário de Brasília)"><Input id="wa-end" type="time" value={config.contact_end} onChange={(event) => update({ contact_end: event.target.value })} /></Field>
          </div>
          <Toggle checked={config.pilot_mode} onChange={(value) => update({ pilot_mode: value, ...deauthorize, contacts: value ? config.contacts.map((contact, index) => ({ ...contact, enabled: index === 0 && contact.enabled })) : config.contacts })} label="Modo piloto" hint="Testar com um único contato antes de liberar para todos." />
          <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
            <Toggle checked={config.pilot_consent_confirmed} onChange={(value) => update({ pilot_consent_confirmed: value })} label="Confirmo que os contatos habilitados autorizaram receber mensagens" />
            <Toggle checked={config.enabled} onChange={(value) => update({ enabled: value })} label="Ativar a Kiara no WhatsApp" hint={`${enabledCount} contato(s) habilitado(s). A automação depende do WhatsApp Web e do computador ligados.`} />
          </div>
        </Section>
      </fieldset>

      <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t bg-background/95 py-3 backdrop-blur">
        <Button type="submit" disabled={saving}>{saving ? <Loader2 className="animate-spin" /> : null}Salvar</Button>
        {formError ? <p role="alert" className="text-sm text-destructive">{formError}</p> : formNotice ? <p role="status" className="text-sm text-muted-foreground">{formNotice}</p> : null}
      </div>
    </form>}

    <details className="rounded-2xl border bg-card px-5 py-4">
      <summary className="cursor-pointer font-medium">Histórico <span className="text-sm font-normal text-muted-foreground">· {activity.length} registro(s)</span></summary>
      {activity.length ? <ol className="mt-4 max-h-96 space-y-2 overflow-y-auto">{activity.map((event) => <li key={event.id} className="rounded-xl border p-3 text-sm">
        <div className="flex flex-wrap justify-between gap-2"><strong>{event.phone || "WhatsApp"} · {activityLabels[event.kind] ?? event.kind}</strong><time dateTime={event.occurred_at} className="text-xs text-muted-foreground">{dateLabel(event.occurred_at)}</time></div>
        {event.text ? <p className="mt-1 whitespace-pre-wrap break-words text-muted-foreground">{event.text}</p> : null}
        <p className="mt-1 text-xs text-muted-foreground">{activityLabels[event.status] ?? event.status}</p>
      </li>)}</ol> : <p className="mt-3 text-sm text-muted-foreground">Nenhuma atividade ainda.</p>}
    </details>
  </div>
}
