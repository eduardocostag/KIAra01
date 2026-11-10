"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { leadDisplayName, type PipelineEntry } from "@/lib/api/pipeline"

type Contact = { phone: string; name: string; enabled: boolean; handoff: boolean }
type Config = { pilot_mode: boolean; daily_limit?: number; auto_reply_enabled?: boolean; followup_enabled?: boolean; initial_outreach_enabled?: boolean; outreach_template?: string; pilot_consent_confirmed: boolean; enabled: boolean; ai_context: string; reply_template: string; followup_template: string; followup_hours: number; contact_start: string; contact_end: string; contacts: Contact[] }
type Activity = { id: string; phone: string; kind: string; text: string; occurred_at: string; status: string }
type Events = { items: Activity[]; last_heartbeat_at: string | null; online: boolean }
type AnalysisJob = { id: string; status: "queued" | "running" | "completed" | "failed"; result?: { imported?: number; duplicates?: number; scanned?: number; skipped?: number; error?: string | null } | null }

function apiErrorMessage(payload: unknown) {
  if (typeof payload !== "object" || payload === null || !("error" in payload)) return null
  const error = payload.error
  return typeof error === "object" && error !== null && "message" in error && typeof error.message === "string"
    ? error.message
    : null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/whatsapp-web/${path}`, { ...init, cache: "no-store", headers: { "Content-Type": "application/json" }, signal: init?.signal ?? AbortSignal.timeout(15000) })
  const text = await response.text()
  let payload: unknown
  try {
    payload = JSON.parse(text)
  } catch {
    const isHtml = response.headers.get("content-type")?.includes("text/html") || /^\s*</.test(text)
    if (isHtml) {
      throw new Error("Não foi possível carregar o WhatsApp. Tente novamente em instantes.")
    }
    throw new Error("A conexão não respondeu como esperado. Tente novamente em instantes.")
  }
  if (!response.ok) throw new Error(apiErrorMessage(payload) ?? "Não foi possível acessar o atendimento.")
  return payload as T
}

const activityLabels: Record<string, string> = {
  inbound: "Mensagem recebida", outbound_observed: "Mensagem enviada observada", reply: "Resposta automática",
  reply_handoff: "Encaminhamento para humano", followup: "Follow-up", heartbeat: "Conexão do executor",
  optout: "Pedido para parar", handoff: "Atendimento humano", resume: "Retomada", error: "Erro",
  recorded: "Registrado", pending: "Na fila", sending: "Enviando", sent: "Enviado",
  confirmed: "Confirmado na conversa", uncertain: "Envio incerto — revisar", cancelled: "Cancelado",
  paused: "Pausado", ready: "WhatsApp conectado", qr_required: "Login por QR necessário", disconnected: "Desconectado",
}

function dateLabel(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "Data indisponível" : date.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })
}

function prepareWhatsApp() {
  const requestId = crypto.randomUUID()
  return new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      window.removeEventListener("message", handleMessage)
      reject(new Error("Extensão Kiara não detectada. Instale-a no Chrome e atualize as guias do site e do WhatsApp Web."))
    }, 45000)
    function handleMessage(event: MessageEvent) {
      if (event.source !== window || event.origin !== window.location.origin) return
      if (event.data?.source !== "kiara-whatsapp-extension"
          || event.data.type !== "whatsapp-ready"
          || event.data.requestId !== requestId) return
      clearTimeout(timeout)
      window.removeEventListener("message", handleMessage)
      if (event.data.error) reject(new Error(event.data.error))
      else resolve()
    }
    window.addEventListener("message", handleMessage)
    window.postMessage({ source: "kiara-app", type: "whatsapp-prepare", requestId }, window.location.origin)
  })
}

async function waitForExecutor() {
  const deadline = Date.now() + 90000
  while (Date.now() < deadline) {
    const value = await request<Events>("events")
    if (value.online) return
    await new Promise(resolve => setTimeout(resolve, 3000))
  }
  throw new Error("Não foi possível conectar. Mantenha a Kiara e o WhatsApp Web abertos no Chrome e tente novamente.")
}

export function WhatsAppWebWorkspace({ entries }: { entries: PipelineEntry[] }) {
  const router = useRouter()
  const [config, setConfig] = useState<Config | null>(null)
  const [savedEnabled, setSavedEnabled] = useState(false)
  const [events, setEvents] = useState<Events | null>(null)
  const [error, setError] = useState("")
  const [configError, setConfigError] = useState("")
  const [formError, setFormError] = useState("")
  const [formNotice, setFormNotice] = useState("")
  const [eventError, setEventError] = useState("")
  const [notice, setNotice] = useState("")
  const [saving, setSaving] = useState(false)
  const [phone, setPhone] = useState("")
  const [name, setName] = useState("")
  const [leadSearch, setLeadSearch] = useState("")
  const [analysis, setAnalysis] = useState<AnalysisJob | null>(null)
  const [analysisStarting, setAnalysisStarting] = useState(false)
  const extensionRequestIdRef = useRef("")
  const configDetailsRef = useRef<HTMLDetailsElement>(null)
  const analysisId = analysis?.id
  const analysisStatus = analysis?.status

  useEffect(() => {
    if (formError && configDetailsRef.current) configDetailsRef.current.open = true
  }, [formError])

  useEffect(() => {
    function handleExtensionMessage(event: MessageEvent) {
      if (event.source !== window || event.origin !== window.location.origin) return
      const message = event.data
      if (message?.source !== "kiara-whatsapp-extension"
          || message.type !== "analysis-status"
          || message.jobId !== extensionRequestIdRef.current) return
      if (message.error) { setNotice(""); setError(message.error) }
      else { setError(""); setNotice("Conversas recebidas. A Kiara está analisando os contatos.") }
    }
    window.addEventListener("message", handleExtensionMessage)
    return () => window.removeEventListener("message", handleExtensionMessage)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void request<Config>("config", { signal: controller.signal }).then(value => { setConfig(value); setSavedEnabled(value.enabled) }).catch(reason => { if (!controller.signal.aborted) setConfigError(reason instanceof Error ? reason.message : "Não foi possível carregar a configuração.") })
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
        setAnalysis(job)
        setError("")
        if (job.status === "completed" && job.result) {
          setNotice(`Análise concluída: ${job.result.imported ?? 0} leads importados, ${job.result.duplicates ?? 0} já existentes; ${job.result.skipped ?? 0} conversas ignoradas.`)
          router.refresh()
        } else if (job.status === "failed") {
          setNotice("")
          setError(job.result?.error ?? "Não foi possível concluir a análise. Verifique o executor e o Ollama.")
        } else {
          timer = setTimeout(() => void refreshAnalysis(), 3000)
        }
      } catch (reason) {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Não foi possível consultar o andamento da análise.")
          timer = setTimeout(() => void refreshAnalysis(), 5000)
        }
      }
    }
    void refreshAnalysis()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [analysisId, analysisStatus, router])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      try {
        const value = await request<Events>("events", { signal: controller.signal })
        if (!controller.signal.aborted) { setEvents(value); setEventError("") }
      } catch { if (!controller.signal.aborted) setEventError("Histórico indisponível. A conexão do executor não pôde ser verificada.") }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => void refresh(), 10000) }
    }
    void refresh()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])

  function update(values: Partial<Config>) { setConfig(current => current ? { ...current, ...values } : current); setFormNotice("") }
  function updateContact(index: number, values: Partial<Contact>) {
    if (!config) return
    const contacts = config.contacts.map((contact, position) => ({
      ...contact,
      ...(values.enabled === true && config.pilot_mode ? { enabled: position === index } : {}),
      ...(position === index ? values : {}),
    }))
    const changedAuthorization = values.enabled !== undefined
    update({ contacts, enabled: changedAuthorization ? false : config.enabled, pilot_consent_confirmed: changedAuthorization ? false : config.pilot_consent_confirmed })
  }
  function addContact() {
    const normalized = phone.replace(/[^0-9]/g, "")
    if (!/^[1-9][0-9]{7,14}$/.test(normalized)) { setFormError("Informe o telefone completo com DDI e DDD, por exemplo 5511999999999."); return }
    if (config?.contacts.some(contact => contact.phone.replace(/[^0-9]/g, "") === normalized)) { setFormError("Esse telefone já está cadastrado."); return }
    if (config) update({ enabled: false, pilot_consent_confirmed: false, contacts: [...config.contacts.map(contact => ({ ...contact, enabled: config.pilot_mode ? false : contact.enabled })), { phone: normalized, name: name.trim() || normalized, enabled: true, handoff: false }] })
    setPhone(""); setName(""); setFormError("")
  }
  function selectPilotLead(entry: PipelineEntry) {
    const normalized = entry.consumer.phone?.replace(/\D/g, "") ?? ""
    if (!/^[1-9][0-9]{7,14}$/.test(normalized)) { setFormError("Esse lead não tem um telefone válido com DDI e DDD. Complete o telefone no CRM."); return }
    if (!config) return
    const existing = config.contacts.find(contact => contact.phone === normalized)
    const contacts = existing
      ? config.contacts.map(contact => ({ ...contact, enabled: contact.phone === normalized || (!config.pilot_mode && contact.enabled), handoff: contact.phone === normalized ? false : contact.handoff }))
      : [...config.contacts.map(contact => ({ ...contact, enabled: config.pilot_mode ? false : contact.enabled })), { phone: normalized, name: leadDisplayName(entry.consumer), enabled: true, handoff: false }]
    update({ enabled: false, pilot_consent_confirmed: false, contacts })
    setLeadSearch("")
    setFormError("")
    setFormNotice("Lead selecionado. Confirme a autorização do contato, salve a configuração e só então habilite as respostas automáticas.")
  }
  const matchingLeads = entries.filter(entry => {
    const normalized = entry.consumer.phone?.replace(/\D/g, "") ?? ""
    const search = leadSearch.trim().toLocaleLowerCase("pt-BR")
    return !["won", "lost"].includes(entry.stage) && /^[1-9][0-9]{7,14}$/.test(normalized) &&
      (!search || `${leadDisplayName(entry.consumer)} ${entry.consumer.phone}`.toLocaleLowerCase("pt-BR").includes(search))
  }).slice(0, 8)
  async function startAnalysis() {
    setAnalysisStarting(true); setError(""); setNotice("")
    try {
      window.open("kiara-whatsapp://analyze", "_blank")
      setNotice("Conectando com sua sessão da Kiara…")
      await prepareWhatsApp()
      await waitForExecutor()
      const job = await request<AnalysisJob>("analysis", { method: "POST", body: JSON.stringify({ limit: 30 }) })
      setAnalysis(job)
      extensionRequestIdRef.current = job.id
      window.postMessage({ source: "kiara-app", type: "whatsapp-analysis", jobId: job.id, limit: 30 }, window.location.origin)
      setNotice("Analisando conversas. Os contatos encontrados aparecerão no CRM.")
    } catch (reason) {
      setNotice("")
      setError(reason instanceof Error ? reason.message : "Não foi possível solicitar a análise.")
    } finally {
      setAnalysisStarting(false)
    }
  }
  async function save(pause = false) {
    if (!config) return
    if (!pause && config.enabled && (!config.pilot_consent_confirmed || !config.contacts.some(contact => contact.enabled && !contact.handoff))) {
      setFormError("Selecione os contatos autorizados e confirme a ativação da operação.")
      return
    }
    if (!pause && config.enabled && !config.ai_context.trim()) {
      setFormError("Informe as informações autorizadas da empresa antes de habilitar a automação.")
      return
    }
    if (!pause && (!Number.isInteger(config.followup_hours) || config.followup_hours < 1 || config.followup_hours > 720 || !config.contact_start || !config.contact_end || config.contact_start >= config.contact_end)) {
      setFormError("Informe um prazo de 1 a 720 horas e um horário de início anterior ao fim.")
      return
    }
    setSaving(true); setFormError(""); setFormNotice("")
    try {
      const source = pause ? await request<Config>("config") : config
      const value = await request<Config>("config", { method: "PUT", body: JSON.stringify({ ...source, enabled: pause ? false : source.enabled }) })
      setConfig(value); setSavedEnabled(value.enabled)
      setFormNotice(value.enabled ? "Operação habilitada. O executor seguirá os contatos, horários e limites configurados." : "Automação pausada. Novos envios automáticos estão desabilitados.")
    } catch (reason) { setFormError(reason instanceof Error ? reason.message : "Falha ao salvar.") }
    finally { setSaving(false) }
  }

  const analysisBusy = analysis?.status === "queued" || analysis?.status === "running"
  const connectionLabel = error ? "Não foi possível concluir" : analysisStarting ? "Conectando…"
    : analysisBusy ? "Analisando conversas…" : eventError ? "Conexão não verificada"
      : events?.online ? "Computador conectado" : events ? "Aguardando conexão" : "Verificando conexão…"
  const connectionDescription = error || notice || (eventError ? "Não conseguimos verificar a conexão agora. Tente novamente."
    : events?.online ? "Sua conexão local está ativa. Você já pode analisar as conversas."
      : "Mantenha a Kiara e o WhatsApp Web abertos no mesmo Chrome.")
  const activity = events?.items.filter(event => event.kind !== "heartbeat") ?? []
  const diagnostics = events?.items.filter(event => event.kind === "heartbeat") ?? []

  return <section className="mx-auto mt-8 max-w-6xl space-y-4" aria-labelledby="whatsapp-heading">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="whatsapp-heading" className="text-xl font-semibold">WhatsApp</h2><p className="mt-1 text-sm text-muted-foreground">Conecte suas conversas ao CRM e acompanhe o atendimento.</p></div>
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">{config ? savedEnabled ? "Automação ativa" : "Automação pausada" : "Automação não verificada"}</span>
        {savedEnabled ? <Button type="button" variant="outline" onClick={() => void save(true)} disabled={saving}>{saving ? "Pausando…" : "Pausar automação"}</Button> : null}
      </div>
    </header>
    <div className="rounded-2xl border bg-card p-5 sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0" role={error ? "alert" : "status"}>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Conexão</p>
          <h3 className="flex items-center gap-2 font-semibold"><span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${error ? "bg-destructive" : events?.online && !eventError ? "bg-emerald-500" : "bg-muted-foreground"}`} />{connectionLabel}</h3>
          <p className={`mt-2 max-w-xl break-words text-sm ${error ? "text-destructive" : "text-muted-foreground"}`}>{connectionDescription}</p>
        </div>
        <Button type="button" className="w-full shrink-0 sm:w-auto" onClick={() => void startAnalysis()} disabled={analysisStarting || analysisBusy}>{analysisStarting ? "Conectando…" : analysisBusy ? "Analisando…" : error ? "Tentar novamente" : "Analisar conversas"}</Button>
      </div>
      <p className="mt-5 border-t pt-4 text-xs text-muted-foreground">Até 30 conversas por análise. Os contatos vão para o CRM; nenhuma mensagem é enviada.</p>
    </div>
    <details ref={configDetailsRef} className="group rounded-2xl border bg-card">
      <summary className="cursor-pointer rounded-2xl p-5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">Configurações da automação<span className="ml-2 text-xs font-normal text-muted-foreground">{config ? `${config.contacts.filter(contact => contact.enabled).length} contato(s) habilitado(s)` : configError ? "Indisponíveis" : "Carregando…"}</span></summary>
      <div className="border-t p-5">
    {!config ? <p className="text-sm text-muted-foreground">{configError || "Carregando configuração…"}</p> : <fieldset disabled={saving} className="space-y-5 disabled:opacity-60">
      <legend className="sr-only">Configuração da automação do WhatsApp</legend>
      {formError ? <p role="alert" className="text-sm text-destructive">{formError}</p> : formNotice ? <p role="status" className="text-sm text-primary">{formNotice}</p> : null}
      <p className="text-sm text-muted-foreground">Defina quem a Kiara pode atender e quais informações ela pode usar. A automação depende do computador e da IA local ligados.</p>
      <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={config.enabled} aria-describedby="wa-read-only-note" onChange={event => update({ enabled: event.target.checked })} />Habilitar a operação autônoma</label>
      <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={config.pilot_consent_confirmed} aria-describedby="wa-read-only-note" onChange={event => update({ pilot_consent_confirmed: event.target.checked })} /><span>Confirmo que os contatos selecionados estão autorizados nesta operação e podem receber respostas e follow-ups conforme a configuração.</span></label>
      <p id="wa-read-only-note" className="text-xs text-muted-foreground">Envios são limitados aos contatos habilitados. Atendimento humano e pedidos para parar pausam a IA; um envio incerto exige revisão antes de repetir.</p>
      <div className="grid gap-4 sm:grid-cols-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={config.pilot_mode} onChange={event => update({ pilot_mode: event.target.checked, enabled: false, pilot_consent_confirmed: false, contacts: event.target.checked ? config.contacts.map((contact, index) => ({ ...contact, enabled: index === 0 && contact.enabled })) : config.contacts })} />Modo piloto: um contato</label><div className="space-y-2"><Label htmlFor="wa-daily-limit">Limite de envios por dia</Label><Input id="wa-daily-limit" type="number" min={1} max={200} value={config.daily_limit ?? 50} onChange={event => update({ daily_limit: Number(event.target.value) })} /></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={config.auto_reply_enabled ?? true} onChange={event => update({ auto_reply_enabled: event.target.checked })} />Responder mensagens com IA</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={config.followup_enabled ?? false} onChange={event => update({ followup_enabled: event.target.checked })} />Executar follow-ups configurados</label></div>
      <div className="grid gap-4 md:grid-cols-3"><div className="space-y-2"><Label htmlFor="wa-followup">Follow-up após (horas)</Label><Input id="wa-followup" type="number" min={1} max={720} value={config.followup_hours} onChange={event => update({ followup_hours: Number(event.target.value) })} /></div><div className="space-y-2"><Label htmlFor="wa-start">Início dos envios (hora, São Paulo)</Label><Input id="wa-start" type="time" value={config.contact_start} onChange={event => update({ contact_start: event.target.value })} /></div><div className="space-y-2"><Label htmlFor="wa-end">Fim dos envios (hora, São Paulo)</Label><Input id="wa-end" type="time" value={config.contact_end} onChange={event => update({ contact_end: event.target.value })} /></div></div>
      <div className="space-y-2"><Label htmlFor="wa-ai-context">Informações autorizadas para a IA</Label><Textarea id="wa-ai-context" maxLength={6000} value={config.ai_context} onChange={event => update({ ai_context: event.target.value })} className="min-h-32" placeholder="Descreva a empresa, serviços, preços aprovados, horários e limites do atendimento." /><p className="text-xs text-muted-foreground">Inclua somente informações públicas/aprovadas para atendimento. Sem esse contexto, a automação não pode ser habilitada; não insira senhas ou dados pessoais de clientes.</p></div>
      <div className="space-y-3 rounded-xl border p-4"><label className="flex items-start gap-2 text-sm font-medium"><input type="checkbox" className="mt-1" checked={config.initial_outreach_enabled ?? false} onChange={event => update({ initial_outreach_enabled: event.target.checked })} /><span>Enviar abordagem inicial aos contatos autorizados sem conversa iniciada</span></label><Label htmlFor="wa-outreach">Mensagem de abordagem inicial</Label><Textarea id="wa-outreach" maxLength={4000} value={config.outreach_template ?? ""} onChange={event => update({ outreach_template: event.target.value })} placeholder="Olá {name}, ..." /><p className="text-xs text-muted-foreground">Uma abordagem inicial por contato. O executor respeita o horário, a pausa, o limite diário e resultados incertos. Esta opção vem desligada.</p></div>
      <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="wa-reply">Mensagem de encaminhamento humano</Label><Textarea id="wa-reply" maxLength={4000} value={config.reply_template} onChange={event => update({ reply_template: event.target.value })} className="min-h-28" /></div><div className="space-y-2"><Label htmlFor="wa-followup-text">Mensagem de follow-up</Label><Textarea id="wa-followup-text" maxLength={4000} value={config.followup_template} onChange={event => update({ followup_template: event.target.value })} className="min-h-28" /></div></div>
      <p className="text-xs text-muted-foreground">As respostas são geradas pelo modelo Ollama configurado no computador executor. Se o modelo estiver indisponível, a Kiara não envia nada e pausa o contato. Quando não houver informação suficiente, usa a mensagem de encaminhamento e pausa para atendimento humano. Use {'{name}'} nessa mensagem para inserir o nome do contato.</p>
      <div className="space-y-3"><h3 className="font-semibold">Selecionar contatos do CRM</h3><div className="space-y-2"><Label htmlFor="wa-lead-search">Buscar por nome ou telefone</Label><Input id="wa-lead-search" value={leadSearch} maxLength={200} onChange={event => setLeadSearch(event.target.value)} placeholder="Digite nome ou telefone do lead autorizado" />{leadSearch.trim() ? matchingLeads.length ? <ul className="max-h-56 divide-y overflow-y-auto rounded-xl border">{matchingLeads.map(entry => <li key={entry.id} className="flex flex-wrap items-center gap-3 p-3"><div className="min-w-0 flex-1"><p className="truncate font-medium">{leadDisplayName(entry.consumer)}</p><p className="text-sm text-muted-foreground">{entry.consumer.phone}</p></div><Button type="button" variant="outline" onClick={() => selectPilotLead(entry)}>Adicionar à operação</Button></li>)}</ul> : <p className="text-sm text-muted-foreground">Nenhum lead com telefone válido corresponde à busca.</p> : <p className="text-xs text-muted-foreground">Busque leads autorizados para esta operação. No modo piloto, somente um contato fica habilitado.</p>}</div>
      <details className="rounded-xl border p-3"><summary className="cursor-pointer text-sm font-medium">Adicionar contato manualmente</summary><div className="mt-3 grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]"><div className="space-y-2"><Label htmlFor="wa-name">Nome</Label><Input id="wa-name" value={name} maxLength={120} onChange={event => setName(event.target.value)} /></div><div className="space-y-2"><Label htmlFor="wa-phone">Telefone com DDI e DDD</Label><Input id="wa-phone" type="tel" placeholder="5511999999999" value={phone} onChange={event => setPhone(event.target.value)} /></div><Button type="button" variant="outline" onClick={addContact}>Adicionar contato</Button></div></details>
      {config.contacts.length ? <ul className="divide-y rounded-xl border">{config.contacts.map((contact, index) => <li key={contact.phone} className="flex flex-wrap items-center gap-4 p-3"><div className="min-w-0 flex-1"><p className="break-words font-medium">{contact.name}</p><p className="text-sm text-muted-foreground">+{contact.phone}</p></div><label className="flex items-center gap-2 text-sm"><input type={config.pilot_mode ? "radio" : "checkbox"} name="wa-pilot-contact" aria-label={`Selecionar ${contact.name} para o piloto`} checked={contact.enabled} onChange={() => updateContact(index, { enabled: !contact.enabled })} />Contato habilitado</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label={`Atendimento humano para ${contact.name}`} checked={contact.handoff} onChange={event => updateContact(index, { handoff: event.target.checked })} />Atendimento humano</label><Button type="button" variant="ghost" aria-label={`Remover ${contact.name}`} onClick={() => update({ enabled: false, pilot_consent_confirmed: false, contacts: config.contacts.filter((_, position) => position !== index) })}>Remover</Button></li>)}</ul> : <p className="text-sm text-muted-foreground">Nenhum contato selecionado. Adicione um contato autorizado do CRM.</p>}</div>
      <Button type="button" onClick={() => void save()}>{saving ? "Salvando…" : "Salvar automação do WhatsApp"}</Button>
    </fieldset>}
      </div>
    </details>
    <details className="rounded-2xl border bg-card">
      <summary className="cursor-pointer rounded-2xl p-5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">Histórico do atendimento<span className="ml-2 text-xs font-normal text-muted-foreground">{activity.length} registro(s)</span></summary>
      <div className="border-t p-5">{eventError ? <p className="text-sm text-muted-foreground">O histórico está indisponível no momento.</p> : activity.length ? <ol className="max-h-96 space-y-3 overflow-y-auto">{activity.map(event => <li key={event.id} className="rounded-xl border p-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><strong>{event.phone || "Atendimento"} · {activityLabels[event.kind] ?? event.kind}</strong><time dateTime={event.occurred_at} className="text-xs text-muted-foreground">{dateLabel(event.occurred_at)}</time></div><p className="mt-2 whitespace-pre-wrap break-words">{event.text}</p><p className="mt-2 text-xs text-muted-foreground">{activityLabels[event.status] ?? event.status}</p></li>)}</ol> : <p className="text-sm text-muted-foreground">{events ? "Nenhuma atividade de atendimento ainda." : "Carregando histórico…"}</p>}</div>
    </details>
    <details className="rounded-2xl border bg-card">
      <summary className="cursor-pointer rounded-2xl p-5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">Ajuda com a conexão</summary>
      <div className="space-y-4 border-t p-5 text-sm text-muted-foreground">
        <ol className="list-decimal space-y-2 pl-5"><li>Abra a Kiara e o WhatsApp Web no mesmo Chrome.</li><li>Ative a extensão Kiara. Se acabou de instalá-la ou atualizá-la, recarregue as duas guias.</li><li>Clique em Analisar conversas. A conexão usa seu login atual da Kiara, sem pedir outra senha.</li></ol>
        <p>Mantenha o computador ligado e o Ollama disponível durante a análise. Conversas sem número verificável são ignoradas.</p>
        <details className="rounded-xl border p-3"><summary className="cursor-pointer font-medium text-foreground">Diagnóstico da conexão<span className="ml-2 text-xs font-normal text-muted-foreground">{diagnostics.length} registro(s)</span></summary><div className="mt-3 space-y-3">
          <p>{eventError ? "Não foi possível verificar o computador." : events?.online ? "O computador está conectado. Isso não confirma o login no WhatsApp Web." : events ? "O computador não está conectado." : "Verificando conexão…"}</p>
          {events?.last_heartbeat_at ? <p>Última sincronização: {dateLabel(events.last_heartbeat_at)}</p> : null}
          {configError ? <p>Configuração: {configError}</p> : null}
          {diagnostics.length ? <ol className="max-h-56 space-y-2 overflow-y-auto">{diagnostics.map(event => <li key={event.id} className="rounded-lg border p-3"><time dateTime={event.occurred_at} className="text-xs">{dateLabel(event.occurred_at)}</time><p className="mt-1">{activityLabels[event.status] ?? event.status}</p></li>)}</ol> : <p>Nenhum registro de conexão disponível.</p>}
        </div></details>
      </div>
    </details>
  </section>
}
