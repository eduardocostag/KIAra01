"use client"

import { useEffect, useRef, useState, useSyncExternalStore } from "react"
import Link from "next/link"
import { ArrowRight, Building2, Camera, Check, Copy, Keyboard, Loader2, MessageCircle, RotateCcw, ScanLine, Sparkles, UserRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { growth, whatsappLink } from "@/lib/api/growth"
import { salesRequest, type SalesProfile } from "@/lib/api/sales"
import { cn } from "@/lib/utils"

type Contact = { name: string; role: string; company: string; phone: string; email: string; website: string; instagram: string; city: string; cnpj: string }
type Company = { cnpj_formatted?: string | null; legal_name?: string | null; trade_name?: string | null; opened_at?: string | null; main_activity?: string | null; active?: boolean | null; partners?: { name: string; role: string }[] }
type Preview = { contact: Contact & { phone_kind: string; other_phones: string[] }; kind: string; site_read: boolean; company: Company | null; decision_maker: { name: string; role: string; source: string } | null }
type Saved = { pipeline_entry_id: string; consumer_id: string; created: boolean; phone: string; display_name: string }
type Step = "capture" | "reading" | "review" | "message"

const EMPTY: Contact = { name: "", role: "", company: "", phone: "", email: "", website: "", instagram: "", city: "", cnpj: "" }
const ADJUSTMENTS = ["Mais curta", "Mais formal", "Mais descontraída", "Proponha uma reunião"]
const EVENT_KEY = "kiara-presencial-event"
const READING = ["Lendo o cartão…", "Conferindo telefones e WhatsApp…", "Buscando a empresa na Receita Federal…"]
const FIELDS: { key: keyof Contact; label: string; type?: string; placeholder?: string }[] = [
  { key: "name", label: "Nome", placeholder: "Nome da pessoa" }, { key: "role", label: "Cargo" }, { key: "company", label: "Empresa" },
  { key: "phone", label: "Telefone / WhatsApp", type: "tel" }, { key: "email", label: "E-mail", type: "email" }, { key: "website", label: "Site" },
  { key: "instagram", label: "Instagram" }, { key: "city", label: "Cidade" },
]

/** A photo from the phone camera, reduced to a light JPEG (the card stays readable, the upload stays small). */
async function compress(file: File): Promise<{ url: string; base64: string }> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement("canvas")
  canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  const url = canvas.toDataURL("image/jpeg", 0.85)
  return { url, base64: url.split(",")[1] ?? "" }
}

function readEvent(): string {
  try { return localStorage.getItem(EVENT_KEY) ?? "" } catch { return "" }
}

function formatPhone(digits: string): string {
  const d = digits.replace(/\D/g, "").replace(/^55(?=\d{10,11}$)/, "")
  return d.length === 11 ? `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}` : d.length === 10 ? `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}` : digits
}

export function PresencialCapture() {
  const [step, setStep] = useState<Step>("capture")
  // The event is remembered for the next contacts of the same fair (per device, a convenience only).
  const remembered = useSyncExternalStore(() => () => undefined, readEvent, () => "")
  const [typed, setTyped] = useState<string | null>(null)
  const event = typed ?? remembered
  function setEvent(value: string) { setTyped(value); try { localStorage.setItem(EVENT_KEY, value) } catch { /* private window */ } }
  const [note, setNote] = useState("")
  const [photo, setPhoto] = useState<string | null>(null)
  const [contact, setContact] = useState<Contact>(EMPTY)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [saved, setSaved] = useState<Saved | null>(null)
  const [message, setMessage] = useState("")
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [busy, setBusy] = useState(false)
  const [reading, setReading] = useState(0)
  const [opened, setOpened] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState("")
  const camera = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (step !== "reading") return
    const timer = window.setInterval(() => setReading((value) => Math.min(READING.length - 1, value + 1)), 2600)
    return () => window.clearInterval(timer)
  }, [step])

  async function read(file: File) {
    setError(""); setReading(0); setStep("reading")
    try {
      const image = await compress(file)
      setPhoto(image.url)
      const result = await growth<Preview>("presencial/read", { method: "POST", body: JSON.stringify({ photo: { mime: "image/jpeg", data_base64: image.base64 } }) })
      setPreview(result)
      setContact({ ...EMPTY, ...result.contact, phone: result.contact.phone ? formatPhone(result.contact.phone) : "" })
      setStep("review")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não consegui ler a foto.")
      setStep("capture")
    }
  }

  async function write(adjust = "") {
    if (!saved) return
    setBusy(true); setError("")
    try { setMessage((await growth<{ message: string }>("sales/draft", { method: "POST", body: JSON.stringify({ pipeline_entry_id: saved.pipeline_entry_id, kind: "first_contact", note: adjust }) })).message) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "A Kiara não conseguiu escrever agora.") }
    finally { setBusy(false) }
  }

  async function save() {
    setBusy(true); setError("")
    try {
      const result = await growth<Saved>("presencial/contacts", { method: "POST", body: JSON.stringify({ ...contact, event, note }) })
      setSaved(result); setStep("message")
      void salesRequest<SalesProfile>("/api/sales/profile").then(setProfile).catch(() => undefined)
      try { setMessage((await growth<{ message: string }>("sales/draft", { method: "POST", body: JSON.stringify({ pipeline_entry_id: result.pipeline_entry_id, kind: "first_contact", note: "" }) })).message) }
      catch { setMessage(`Oi, ${contact.name.split(" ")[0] || "tudo bem"}! Foi um prazer conversar com você${event ? ` na ${event}` : ""}. Podemos continuar a conversa por aqui?`) }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível salvar o contato.") }
    finally { setBusy(false) }
  }

  async function record(status: "opened" | "sent") {
    if (!saved) return
    await salesRequest("/api/sales/activities", { method: "POST", body: JSON.stringify({ pipeline_entry_id: saved.pipeline_entry_id, channel: "whatsapp", status, body: message, follow_up_hours: status === "sent" ? profile?.follow_up_hours ?? 48 : null }) })
  }

  function restart() {
    setStep("capture"); setPhoto(null); setContact(EMPTY); setPreview(null); setSaved(null); setMessage(""); setNote(""); setOpened(false); setSent(false); setError("")
  }

  const link = saved ? whatsappLink(message, null, saved.phone || contact.phone) : null
  const company = preview?.company
  const person = preview?.decision_maker

  return <div className="mx-auto w-full max-w-xl space-y-4">
    <ol className="flex items-center gap-1.5 text-xs text-muted-foreground" aria-label="Etapas">
      {[["capture", "Foto"], ["review", "Conferir"], ["message", "Mensagem"]].map(([key, label], index) => {
        const order = ["capture", "review", "message"], now = order.indexOf(step === "reading" ? "capture" : step)
        return <li key={key} className={cn("flex flex-1 items-center gap-1.5 rounded-full border px-3 py-1.5", index <= now && "border-primary/40 bg-primary/10 text-foreground")}>
          <span className={cn("grid size-5 place-items-center rounded-full border text-[11px]", index < now && "border-emerald-400 bg-emerald-400/20 text-emerald-300")}>{index < now ? <Check className="size-3" /> : index + 1}</span>{label}
        </li>
      })}
    </ol>

    {step === "capture" || step === "reading" ? <section className="kiara-soft-panel space-y-5 rounded-2xl border p-5 sm:p-6">
      <div className="space-y-1.5">
        <label htmlFor="presencial-event" className="text-sm font-medium">Onde vocês se conheceram?</label>
        <input id="presencial-event" value={event} onChange={(e) => setEvent(e.target.value.slice(0, 80))} placeholder="Ex.: Expo Sul 2026, visita ao cliente, almoço da ACI" className="h-11 w-full rounded-xl border bg-background px-3 outline-none focus:border-primary/50" />
        <p className="text-xs text-muted-foreground">Fica salvo para os próximos contatos do mesmo evento.</p>
      </div>
      <input ref={camera} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void read(file) }} />
      {step === "reading" ? <div className="relative overflow-hidden rounded-2xl border bg-black/40">
        {/* eslint-disable-next-line @next/next/no-img-element -- local photo preview (data URL) */}
        {photo ? <img src={photo} alt="Foto do cartão" className="max-h-72 w-full object-contain opacity-70" /> : <div className="h-56" />}
        <div className="absolute inset-x-0 h-1 animate-[presencial-scan_1.6s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-primary to-transparent shadow-[0_0_24px_rgb(124_77_255)]" />
        <p className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-2 bg-black/60 p-3 text-sm"><Loader2 className="size-4 animate-spin" />{READING[reading]}</p>
      </div> : <button type="button" onClick={() => camera.current?.click()} className="group flex w-full flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-primary/40 bg-primary/5 px-4 py-10 text-center transition hover:border-primary hover:bg-primary/10">
        <span className="grid size-16 place-items-center rounded-2xl bg-primary/20 text-primary shadow-[0_0_40px_-8px_rgb(124_77_255)] transition group-hover:scale-105"><Camera className="size-8" /></span>
        <span className="text-lg font-medium">Fotografar cartão ou crachá</span>
        <span className="text-sm text-muted-foreground">A Kiara lê os dados, encontra a empresa e prepara a mensagem.</span>
      </button>}
      {step === "capture" ? <Button type="button" variant="ghost" className="w-full text-muted-foreground" onClick={() => { setContact(EMPTY); setPreview(null); setStep("review") }}><Keyboard />Digitar os dados</Button> : null}
      {error ? <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}
    </section> : null}

    {step === "review" ? <section className="kiara-soft-panel space-y-5 rounded-2xl border p-5 sm:p-6 fx-rise">
      <header className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- local photo preview (data URL) */}
        {photo ? <img src={photo} alt="Cartão fotografado" className="h-16 w-24 shrink-0 rounded-lg border object-cover" /> : <span className="grid size-12 place-items-center rounded-xl bg-primary/15 text-primary"><ScanLine /></span>}
        <div><h2 className="text-lg font-medium">{preview ? "Confira o que a Kiara leu" : "Dados do contato"}</h2><p className="text-sm text-muted-foreground">{preview ? "Corrija o que precisar antes de salvar." : "Preencha pelo menos o nome e um telefone ou e-mail."}</p></div>
      </header>
      <div className="grid gap-3 sm:grid-cols-2">{FIELDS.map((field) => <label key={field.key} className={cn("grid gap-1 text-sm", (field.key === "name" || field.key === "company") && "sm:col-span-2")}>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">{field.label}{field.key === "phone" && preview?.contact.phone_kind === "celular" && contact.phone ? <span className="rounded-full bg-emerald-400/15 px-1.5 text-[10px] text-emerald-300">celular · WhatsApp</span> : null}</span>
        <input type={field.type ?? "text"} value={contact[field.key]} placeholder={field.placeholder} onChange={(e) => setContact({ ...contact, [field.key]: e.target.value })} className="h-10 rounded-lg border bg-background px-3 outline-none focus:border-primary/50" />
      </label>)}</div>
      {preview?.contact.other_phones.length ? <p className="text-xs text-muted-foreground">Outros telefones no cartão: {preview.contact.other_phones.map(formatPhone).join(", ")}</p> : null}
      {company || person ? <div className="space-y-2 rounded-xl border border-sky-400/25 bg-sky-400/5 p-4 text-sm">
        <p className="flex items-center gap-2 font-medium text-sky-200"><Building2 className="size-4" />Encontrado em fontes públicas</p>
        {company ? <ul className="space-y-0.5 text-muted-foreground">
          <li><span className="text-foreground">{company.legal_name || company.trade_name}</span>{company.cnpj_formatted ? ` · CNPJ ${company.cnpj_formatted}` : ""}</li>
          {company.main_activity ? <li>{company.main_activity}</li> : null}
          {company.opened_at ? <li>Aberta em {company.opened_at.slice(0, 4)}{company.active === false ? " · situação irregular" : ""}</li> : null}
        </ul> : null}
        {person ? <p className="flex items-center gap-2"><UserRound className="size-4 text-sky-300" />Responsável: <span className="font-medium">{person.name}</span>{person.role ? <span className="text-muted-foreground">({person.role})</span> : null}</p> : null}
      </div> : null}
      <label className="grid gap-1 text-sm"><span className="text-xs text-muted-foreground">O que vocês conversaram? (a Kiara usa na mensagem)</span>
        <textarea value={note} onChange={(e) => setNote(e.target.value.slice(0, 600))} rows={3} placeholder="Ex.: quer orçamento para 3 unidades até março; prefere falar à tarde" className="resize-y rounded-lg border bg-background p-3 outline-none focus:border-primary/50" />
      </label>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      <div className="flex gap-2">
        <Button type="button" variant="outline" onClick={restart}><RotateCcw />Outra foto</Button>
        <Button type="button" className="flex-1" disabled={busy} onClick={() => void save()}>{busy ? <Loader2 className="animate-spin" /> : <Check />}Salvar e preparar mensagem</Button>
      </div>
    </section> : null}

    {step === "message" && saved ? <section className="kiara-soft-panel space-y-5 rounded-2xl border p-5 sm:p-6 fx-rise">
      <header className="space-y-1">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[.16em] text-emerald-300"><Check className="size-3.5" />{saved.created ? "Contato salvo no CRM" : "Contato atualizado no CRM"}</p>
        <h2 className="text-xl font-medium">{saved.display_name}</h2>
        {event ? <p className="text-sm text-muted-foreground">Conheceu em {event}</p> : null}
      </header>
      <div className="space-y-2">
        <div className="flex items-center gap-2"><span className="text-sm font-medium">Primeira mensagem</span>{busy ? <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground"><Sparkles className="size-3.5 text-primary" />A Kiara está escrevendo…</span> : null}</div>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={6} disabled={busy && !message} className="w-full resize-y rounded-xl border bg-background p-3 text-[15px] leading-6 outline-none focus:border-primary/50" />
        <div className="flex flex-wrap gap-1.5">{ADJUSTMENTS.map((adjust) => <button key={adjust} type="button" disabled={busy} onClick={() => void write(adjust)} className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground disabled:opacity-50"><RotateCcw className="mr-1 inline size-3" />{adjust}</button>)}</div>
        <p className="text-xs text-muted-foreground">Sai do seu WhatsApp, sem risco para o número. Quando a pessoa responder, a Kiara continua a conversa.</p>
      </div>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      {sent ? <div className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-4 text-sm">
        <p className="font-medium text-emerald-200">Envio registrado.</p><p className="text-muted-foreground">Lead em &quot;Em contato&quot; com acompanhamento agendado para {profile?.follow_up_hours ?? 48} horas.</p>
      </div> : <div className="flex items-center gap-2">
        {link ? <Button asChild size="lg" className="flex-1 bg-emerald-500 text-white hover:bg-emerald-600"><a href={link} target="_blank" rel="noopener noreferrer" onClick={() => { setOpened(true); void record("opened").catch(() => undefined) }}><MessageCircle />Abrir no WhatsApp</a></Button>
          : <Button type="button" size="lg" variant="outline" className="flex-1" onClick={() => void navigator.clipboard.writeText(message).then(() => setOpened(true))}><Copy />Copiar mensagem</Button>}
        <Button type="button" size="lg" variant={opened ? "default" : "outline"} disabled={busy || !message.trim()} onClick={() => void record("sent").then(() => setSent(true)).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Não foi possível registrar."))}><Check />Enviei</Button>
      </div>}
      <div className="flex flex-wrap gap-2 border-t pt-4">
        <Button type="button" onClick={restart}><Camera />Próximo contato</Button>
        <Button asChild variant="ghost"><Link href={`/app/leads/${encodeURIComponent(saved.consumer_id)}`}>Ver no CRM<ArrowRight /></Link></Button>
      </div>
    </section> : null}
  </div>
}
