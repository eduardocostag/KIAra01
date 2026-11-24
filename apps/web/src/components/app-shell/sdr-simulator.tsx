"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { ArrowLeft, ArrowUp, Bot, Check, Clock, Copy, FlaskConical, Hand, LoaderCircle, RotateCcw, ShieldCheck, SlidersHorizontal, Workflow } from "lucide-react"
import { ImmersiveShell } from "@/components/app-shell/immersive-shell"
import { Button } from "@/components/ui/button"
import { temperatureLabels } from "@/lib/api/inbox-contract"
import { cn } from "@/lib/utils"

type Line = { id: string; from: "lead" | "kiara" | "system"; text: string; caption?: string }
type Analysis = { stage: string; temperature: string; score: number; summary: string; intent: string; next_action: string; gaps: string[] }
type Turn = { action: "reply" | "followup" | "handoff" | "optout" | "none"; reply: string; reason: string; analysis: Analysis | null; memory: string[]; notes: string[]; configured: boolean; mode: string }

const FOLLOWUP_MAX = 2
const stageLabels: Record<string, string> = { new: "Novo", contacted: "Em contato", qualified: "Qualificado", opportunity: "Oportunidade", lost: "Perdido" }
const modeCaption: Record<string, string> = {
  approval: "No WhatsApp real, iria para Aprovações antes de sair",
  auto: "No WhatsApp real, sairia sozinha (modo automático)",
  off: "Atendimento automático desligado: no WhatsApp real nada sairia",
}
const footerLink = "flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground"

let sequence = 0
const line = (from: Line["from"], text: string, caption?: string): Line => ({ id: `l${++sequence}`, from, text, caption })

/** Admin test bench for the WhatsApp SDR: the admin plays the customer and the Kiara answers with the same rules
 *  as on the real number (stop requests, handoff, no link first, follow-up limit). Nothing is sent or stored. */
export function SdrSimulator() {
  const [name, setName] = useState("Mariana Costa")
  const [origin, setOrigin] = useState<"inbound" | "hunted">("inbound")
  const [profile, setProfile] = useState({ company: "", segment: "", city: "", notes: "" })
  const [approach, setApproach] = useState("")
  const [copied, setCopied] = useState(false)
  const [lines, setLines] = useState<Line[]>([])
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [ended, setEnded] = useState("")
  const [followups, setFollowups] = useState(0)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [memory, setMemory] = useState<string[]>([])
  const [configured, setConfigured] = useState(true)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }) }, [lines.length, busy])

  const lastTalk = [...lines].reverse().find((item) => item.from !== "system")
  const canFollowUp = !busy && !ended && lastTalk?.from === "kiara" && lines.some((item) => item.from === "lead") && followups < FOLLOWUP_MAX

  async function turn(history: Line[], followup: number) {
    setBusy(true); setError("")
    try {
      const response = await fetch("/api/sdr/simulate", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(95_000),
        body: JSON.stringify({ name: name.trim() || "Cliente", followup, memory, origin, ...profile,
          messages: history.filter((item) => item.from !== "system").slice(-40).map((item) => ({ direction: item.from === "lead" ? "inbound" : "outbound", body: item.text.slice(0, 1500) })) }),
      })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível simular agora.")
      const result = body as Turn
      setConfigured(result.configured)
      if (result.analysis) setAnalysis(result.analysis)
      setMemory(result.memory ?? [])
      const added: Line[] = []
      if (result.action === "optout") { setEnded("O cliente pediu para parar. A Kiara não escreve mais para ele."); added.push(line("system", "Pedido de parar: a Kiara não responde mais este contato")) }
      if (result.action === "handoff") {
        if (result.reply) added.push(line("kiara", result.reply, modeCaption[result.mode]))
        added.push(line("system", `Passou para o atendente: ${result.reason}`))
        setEnded("A Kiara passou a conversa para um atendente humano e parou de responder.")
      }
      if (result.action === "reply" || result.action === "followup") added.push(line("kiara", result.reply, [result.action === "followup" ? `Follow-up ${followup} de ${FOLLOWUP_MAX}` : "", modeCaption[result.mode]].filter(Boolean).join(" · ")))
      for (const note of result.notes) if (!note.startsWith("Follow-up") && result.action !== "optout" && result.action !== "handoff") added.push(line("system", note))
      if (followup) setFollowups(followup)
      setLines((current) => [...current, ...added])
    } catch (reason) {
      setError(reason instanceof DOMException ? "A Kiara demorou demais para responder. Tente de novo." : reason instanceof Error ? reason.message : "Não foi possível simular agora.")
    } finally { setBusy(false) }
  }

  function send() {
    const text = draft.trim()
    if (!text || busy || ended) return
    // A prospected contact: the conversation starts with the approach the business sent (written by you, not the AI).
    const opening = !lines.length && origin === "hunted" && approach.trim() ? [line("kiara", approach.trim().slice(0, 1500), "Sua abordagem de prospecção")] : []
    const history = [...lines, ...opening, line("lead", text)]
    setLines(history); setDraft(""); setFollowups(0)
    void turn(history, 0)
  }

  async function copy() {
    const who = name.trim() || "Cliente"
    const text = [
      `Simulador da Kiara · ${origin === "hunted" ? "contato prospectado" : "contato que procurou a empresa"} · ${who}`,
      ...Object.entries({ Empresa: profile.company, Segmento: profile.segment, Cidade: profile.city, Anotações: profile.notes }).filter(([, value]) => value.trim()).map(([key, value]) => `${key}: ${value.trim()}`),
      "",
      ...lines.map((item) => item.from === "system" ? `[${item.text}]` : `${item.from === "lead" ? who : "Kiara"}: ${item.text}`),
      ...(analysis ? ["", "O que a Kiara entendeu:", `Etapa: ${stageLabels[analysis.stage] ?? analysis.stage} · Nível: ${temperatureLabels[analysis.temperature] ?? analysis.temperature} · Nota: ${analysis.score}/100`,
        analysis.summary, `Próxima ação: ${analysis.next_action}`, ...(analysis.gaps.length ? [`Falta descobrir: ${analysis.gaps.join("; ")}`] : [])] : []),
      ...(memory.length ? [`Lembraria: ${memory.join("; ")}`] : []),
    ].join("\n")
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch { setError("Não foi possível copiar. Selecione o texto da conversa e copie manualmente.") }
  }

  function silence() {
    if (!canFollowUp) return
    const next = followups + 1
    setLines((current) => [...current, line("system", next === 1 ? "O cliente ficou em silêncio (no real: depois do prazo configurado)" : "Mais alguns dias de silêncio")])
    void turn(lines, next)
  }

  function restart() {
    setLines([]); setDraft(""); setError(""); setEnded(""); setFollowups(0); setAnalysis(null); setMemory([])
  }

  const sidebar = (close: () => void) => <div className="space-y-5 px-1">
    <Link href="/app/whatsapp" onClick={close} className={footerLink}><ArrowLeft className="size-4" aria-hidden="true" />Conversas</Link>
    <fieldset className="space-y-1.5" disabled={lines.length > 0}>
      <legend className="mb-1.5 text-xs font-medium text-sidebar-foreground/70">Como o cliente chegou</legend>
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-sidebar-foreground/5 p-1">
        {([["inbound", "Procurou a empresa"], ["hunted", "Foi prospectado"]] as const).map(([key, label]) =>
          <button key={key} type="button" aria-pressed={origin === key} onClick={() => setOrigin(key)}
            className={cn("min-h-9 rounded-md px-1.5 text-xs font-medium leading-tight transition-colors disabled:opacity-60", origin === key ? "bg-primary text-primary-foreground" : "text-sidebar-foreground/70 hover:bg-sidebar-foreground/5")}>{label}</button>)}
      </div>
      {lines.length ? <p className="text-[11px] text-sidebar-foreground/50">Recomece o teste para mudar.</p> : null}
    </fieldset>
    <Field label="Nome do cliente" value={name} max={80} onChange={setName} />
    <details className="group space-y-2" open={origin === "hunted" || undefined}>
      <summary className="cursor-pointer list-none text-xs font-medium text-sidebar-foreground/70 marker:hidden">Cadastro do cliente <span className="font-normal text-sidebar-foreground/50">(opcional)</span></summary>
      <div className="mt-2 space-y-2">
        <Field label="Empresa" value={profile.company} max={160} placeholder="Ex.: Clínica Bela" onChange={(company) => setProfile((current) => ({ ...current, company }))} />
        <Field label="Segmento" value={profile.segment} max={160} placeholder="Ex.: estética" onChange={(segment) => setProfile((current) => ({ ...current, segment }))} />
        <Field label="Cidade" value={profile.city} max={120} placeholder="Ex.: Campinas" onChange={(city) => setProfile((current) => ({ ...current, city }))} />
        <Field label="Anotações / preferências" value={profile.notes} max={600} placeholder="Ex.: prefere contato à tarde" multiline onChange={(notes) => setProfile((current) => ({ ...current, notes }))} />
      </div>
    </details>
    {origin === "hunted" && !lines.length ? <Field label="Sua mensagem de abordagem" value={approach} max={1500} multiline
      placeholder={`Ex.: Oi, ${name.split(" ")[0] || "tudo bem"}! Vi a ${profile.company || "sua empresa"} no Google e tenho uma ideia para trazer mais clientes. Posso te contar?`}
      onChange={setApproach} /> : null}
    <section aria-label="Análise da Kiara" className="space-y-3 text-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-sidebar-foreground/55">O que a Kiara entendeu</p>
      {analysis ? <>
        <div className="space-y-2 text-center">
          <Stat label="Etapa do funil" value={stageLabels[analysis.stage] ?? analysis.stage} />
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Nível" value={temperatureLabels[analysis.temperature] ?? analysis.temperature} />
            <Stat label="Nota" value={`${analysis.score} de 100`} />
          </div>
        </div>
        {analysis.summary ? <p className="text-sidebar-foreground/80">{analysis.summary}</p> : null}
        {analysis.next_action ? <div><p className="text-xs font-medium text-sidebar-foreground/60">Próxima ação</p><p className="mt-0.5 text-sidebar-foreground/80">{analysis.next_action}</p></div> : null}
        {analysis.gaps.length ? <div><p className="text-xs font-medium text-sidebar-foreground/60">Falta descobrir</p><ul className="mt-0.5 list-inside list-disc text-sidebar-foreground/80">{analysis.gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul></div> : null}
        {memory.length ? <div><p className="text-xs font-medium text-sidebar-foreground/60">Lembraria do contato</p><ul className="mt-0.5 list-inside list-disc text-sidebar-foreground/80">{memory.map((fact, index) => <li key={index}>{fact}</li>)}</ul></div> : null}
      </> : <p className="text-xs text-sidebar-foreground/55">Mande a primeira mensagem como cliente. A análise do lead aparece aqui.</p>}
    </section>
  </div>

  return <ImmersiveShell
    label="Simulador do WhatsApp"
    sidebar={sidebar}
    footer={<><Link href="/app/whatsapp/atendimento" className={footerLink}><SlidersHorizontal className="size-4" aria-hidden="true" />Configurar atendimento</Link><Link href="/app/whatsapp/automacao" className={footerLink}><Workflow className="size-4" aria-hidden="true" />Automação</Link></>}
    topBar={<>
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/15 text-primary"><FlaskConical className="size-4" aria-hidden="true" /></span>
      <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">Simulador</p><p className="truncate text-xs text-muted-foreground">Você é {name.trim() || "Cliente teste"} · nada é enviado</p></div>
      <Button type="button" size="sm" variant="outline" disabled={!canFollowUp} onClick={silence} title="Simula o cliente sem responder, para ver o follow-up"><Clock /><span className="hidden sm:inline">Cliente sumiu</span></Button>
      <Button type="button" size="sm" variant="ghost" disabled={!lines.length} onClick={() => void copy()} aria-label="Copiar conversa e análise" title="Copia a conversa e a análise para colar onde quiser">{copied ? <Check /> : <Copy />}<span className="hidden sm:inline">{copied ? "Copiado" : "Copiar"}</span></Button>
      <Button type="button" size="sm" variant="ghost" disabled={busy || !lines.length} onClick={restart}><RotateCcw /><span className="hidden sm:inline">Recomeçar</span></Button>
    </>}
  >
    <div className="min-h-0 flex-1 overflow-y-auto" role="log" aria-label="Conversa simulada" aria-live="polite">
      <div className="mx-auto w-full max-w-3xl px-4 py-6">
        <div className="mb-4 flex items-start gap-2.5 rounded-2xl border border-primary/25 bg-primary/5 p-3 text-sm">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <p className="text-muted-foreground"><span className="font-medium text-foreground">Modo teste, só para administradores.</span> Você escreve como se fosse o cliente e a Kiara responde com as mesmas regras do WhatsApp real. Nada vai para o WhatsApp e nada fica salvo.</p>
        </div>
        {!configured ? <p role="status" className="mb-4 rounded-2xl border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-200">O atendimento ainda não foi configurado. Preencha <Link href="/app/whatsapp/atendimento" className="underline underline-offset-4">Configurar atendimento</Link> (nicho, serviços e preços) para respostas melhores.</p> : null}
        {!lines.length ? <div className="py-12 text-center">
          <span className="mx-auto mb-3 grid size-12 place-items-center rounded-full border bg-card text-emerald-400"><Bot className="size-5" aria-hidden="true" /></span>
          {origin === "hunted" ? <>
            <p className="text-lg font-medium">Cliente prospectado</p>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">Escreva na lateral a abordagem que a empresa mandou e responda aqui como o cliente. Ideias: &quot;Quem é você?&quot;, &quot;Não tenho interesse&quot; ou &quot;Como funciona?&quot;.</p>
          </> : <>
            <p className="text-lg font-medium">Comece como um cliente</p>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">Ideias: &quot;Oi, quanto custa?&quot;, &quot;Quero fechar, me liga?&quot; ou &quot;Pare de me mandar mensagem&quot;.</p>
          </>}
        </div> : lines.map((item, index) => {
          if (item.from === "system") return <div key={item.id} className="my-3 flex justify-center"><span className="max-w-[90%] rounded-full border bg-background/80 px-3 py-1 text-center text-[11px] font-medium text-muted-foreground">{item.text}</span></div>
          const mine = item.from === "lead"
          const grouped = lines[index - 1]?.from === item.from
          return <div key={item.id} className={cn("flex fx-rise", mine ? "justify-end" : "justify-start", grouped ? "mt-0.5" : "mt-3")}>
            <div className={cn("max-w-[80%] rounded-2xl px-3 pb-1.5 pt-2 shadow-sm", mine ? "rounded-br-md bg-primary/20" : "rounded-bl-md bg-muted")}>
              {!mine && !grouped ? <p className="mb-0.5 flex items-center gap-1 text-[11px] font-medium text-emerald-400"><Bot className="size-3" aria-hidden="true" />Kiara</p> : null}
              <p className="whitespace-pre-wrap break-words text-[15px] leading-6">{item.text}</p>
              {item.caption ? <p className="mt-0.5 text-[11px] leading-4 text-muted-foreground">{item.caption}</p> : null}
            </div>
          </div>
        })}
        {busy ? <div className="mt-3 flex justify-start"><span className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-muted px-3 py-2 text-sm text-muted-foreground"><LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" />Kiara está digitando…</span></div> : null}
        <div ref={endRef} />
      </div>
    </div>
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      {ended ? <div className="flex flex-col items-center gap-2 rounded-3xl border bg-card p-4 text-center text-sm">
        <p className="flex items-center gap-1.5 text-muted-foreground"><Hand className="size-4" aria-hidden="true" />{ended}</p>
        <Button type="button" size="sm" onClick={restart}><RotateCcw />Recomeçar o teste</Button>
      </div> : <div className="rounded-3xl border bg-card px-3 pb-2 pt-3 shadow-sm focus-within:border-primary/40">
        <label htmlFor="sim-message" className="sr-only">Mensagem como cliente</label>
        <textarea id="sim-message" rows={1} maxLength={1500} value={draft} disabled={busy}
          placeholder="Escreva como se fosse o cliente"
          onChange={(event) => setDraft(event.target.value)}
          onInput={(event) => { const element = event.currentTarget; element.style.height = "auto"; element.style.height = `${Math.min(element.scrollHeight, 180)}px` }}
          onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send() } }}
          className="max-h-44 min-h-7 w-full resize-none bg-transparent px-1 text-[15px] leading-6 outline-none placeholder:text-muted-foreground disabled:opacity-60" />
        <div className="mt-1 flex items-center">
          <span className="px-1 text-[11px] text-muted-foreground">{followups ? `Follow-ups usados: ${followups} de ${FOLLOWUP_MAX}` : "Modo teste"}</span>
          <Button type="button" size="icon" className="ml-auto size-9 rounded-full" aria-label="Enviar como cliente" disabled={busy || !draft.trim()} onClick={send}>{busy ? <LoaderCircle className="animate-spin" /> : <ArrowUp />}</Button>
        </div>
      </div>}
      {error ? <p role="alert" className="mt-2 text-center text-sm text-destructive">{error}</p> : null}
    </div>
  </ImmersiveShell>
}

function Field({ label, value, max, placeholder, multiline = false, onChange }: { label: string; value: string; max: number; placeholder?: string; multiline?: boolean; onChange: (value: string) => void }) {
  const className = "w-full rounded-lg bg-sidebar-foreground/5 px-2.5 text-sm outline-none placeholder:text-sidebar-foreground/40 focus-visible:ring-2 focus-visible:ring-sidebar-ring"
  return <label className="block space-y-1"><span className="text-xs text-sidebar-foreground/65">{label}</span>
    {multiline
      ? <textarea value={value} maxLength={max} rows={3} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className={cn(className, "resize-none py-2")} />
      : <input value={value} maxLength={max} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className={cn(className, "h-9")} />}
  </label>
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-sidebar-foreground/5 px-1.5 py-2"><p className="text-[10px] uppercase tracking-wide text-sidebar-foreground/55">{label}</p><p className="mt-0.5 truncate text-sm font-semibold">{value}</p></div>
}
