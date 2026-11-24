"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { BadgeCheck, Check, CircleAlert, Copy, CreditCard, ExternalLink, LoaderCircle, RefreshCw, ShieldCheck, Unplug } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

type OfficialStatus = {
  connected: boolean; platform_ready: boolean; app_id: string; config_id: string; graph_version: string
  display_phone_number?: string; verified_name?: string; quality_rating?: string; registered?: boolean; manager_url?: string
  missing_settings?: string[]; webhook_url?: string; verify_token?: string
}
type ManualForm = { access_token: string; waba_id: string; phone_number_id: string; app_secret: string }
const EMPTY_FORM: ManualForm = { access_token: "", waba_id: "", phone_number_id: "", app_secret: "" }
type SessionInfo = { waba_id: string; phone_number_id: string }
type FacebookSdk = {
  init(options: { appId: string; autoLogAppEvents: boolean; xfbml: boolean; version: string }): void
  login(callback: (response: { authResponse?: { code?: string } | null }) => void, options: Record<string, unknown>): void
}
declare global { interface Window { FB?: FacebookSdk; fbAsyncInit?: () => void } }

async function officialRequest<T>(action: "status" | "connect" | "connect-manual" | "disconnect", body?: unknown): Promise<T> {
  const response = await fetch(`/api/whatsapp-official/${action}`, {
    method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(action.startsWith("connect") ? 60_000 : 20_000),
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof payload?.error?.message === "string" ? payload.error.message : "Não foi possível falar com a Kiara.")
  return payload as T
}

/** Loads Meta's JavaScript SDK once, only when the client decides to connect. */
function loadFacebookSdk(appId: string, version: string): Promise<FacebookSdk> {
  if (window.FB) return Promise.resolve(window.FB)
  return new Promise((resolve, reject) => {
    window.fbAsyncInit = () => {
      window.FB!.init({ appId, autoLogAppEvents: true, xfbml: false, version })
      resolve(window.FB!)
    }
    const script = document.createElement("script")
    script.src = "https://connect.facebook.net/en_US/sdk.js"
    script.async = true
    script.crossOrigin = "anonymous"
    script.onerror = () => reject(new Error("Não foi possível abrir a Meta. Desative bloqueadores de anúncio para este site e tente de novo."))
    document.body.appendChild(script)
  })
}

const qualityLabels: Record<string, { label: string; tone: string }> = {
  GREEN: { label: "Qualidade alta", tone: "text-emerald-400" }, YELLOW: { label: "Qualidade média", tone: "text-amber-400" },
  RED: { label: "Qualidade baixa", tone: "text-destructive" },
}

const GUIDE: { title: string; text: string; href?: string }[] = [
  { title: "Crie o app na Meta", text: "Em Meta for Developers, clique em Criar app, escolha o tipo Empresa e ligue ao portfólio da sua empresa. Depois adicione o produto WhatsApp.", href: "https://developers.facebook.com/apps" },
  { title: "Cadastre o seu número", text: "No app, abra WhatsApp → Configuração da API, adicione e confirme o número. Ali aparecem o Identificador do número de telefone e o Identificador da conta do WhatsApp Business." },
  { title: "Gere o token permanente", text: "Em Configurações do negócio → Usuários do sistema, crie um usuário Admin, dê acesso ao app e à conta do WhatsApp e clique em Gerar token com validade Nunca e as permissões whatsapp_business_management e whatsapp_business_messaging.", href: "https://business.facebook.com/settings/system-users" },
  { title: "Copie a chave secreta", text: "No app, em Configurações do app → Básico, clique em Mostrar na Chave secreta do aplicativo." },
  { title: "Cadastre o pagamento", text: "No WhatsApp Manager, adicione seu cartão. A Meta cobra as conversas direto de você.", href: "https://business.facebook.com/wa/manage/home/" },
]

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  return <div className="min-w-0 space-y-1">
    <p className="text-xs text-muted-foreground">{label}</p>
    <div className="flex items-center gap-2">
      <code className="min-w-0 flex-1 break-all rounded-md border bg-muted/40 px-2 py-1.5 text-xs">{value}</code>
      <Button type="button" variant="outline" size="icon" className="size-8 shrink-0" aria-label={`Copiar ${label}`}
        onClick={() => { void navigator.clipboard.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) }) }}>
        {copied ? <Check /> : <Copy />}</Button>
    </div>
  </div>
}

/** The client's own Meta app: they do everything at Meta and paste 4 values; Kiara only syncs. */
function ManualConnect({ onConnected, disabled }: { onConnected: () => Promise<void>; disabled: boolean }) {
  const [form, setForm] = useState<ManualForm>(EMPTY_FORM)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState("")
  const fields: { key: keyof ManualForm; label: string; hint: string; secret?: boolean; numeric?: boolean }[] = [
    { key: "phone_number_id", label: "Identificador do número de telefone", hint: "Só números", numeric: true },
    { key: "waba_id", label: "Identificador da conta do WhatsApp Business", hint: "Só números", numeric: true },
    { key: "access_token", label: "Token permanente", hint: "Começa com EAA…", secret: true },
    { key: "app_secret", label: "Chave secreta do aplicativo", hint: "32 letras e números", secret: true },
  ]
  const ready = /^\d{5,30}$/.test(form.phone_number_id.trim()) && /^\d{5,30}$/.test(form.waba_id.trim())
    && form.access_token.trim().length >= 40 && /^[0-9a-fA-F]{32}$/.test(form.app_secret.trim())

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!ready) return
    setSending(true); setError("")
    try {
      await officialRequest("connect-manual", Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()])))
      setForm(EMPTY_FORM)
      await onConnected()
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível conectar.") }
    finally { setSending(false) }
  }

  return <div className="space-y-4">
    <ol className="space-y-3">
      {GUIDE.map((step, index) => <li key={step.title} className="flex gap-3 text-sm">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">{index + 1}</span>
        <div className="min-w-0"><p className="font-medium">{step.title}</p><p className="text-muted-foreground">{step.text}</p>
          {step.href ? <a href={step.href} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline">Abrir na Meta<ExternalLink className="size-3" /></a> : null}</div>
      </li>)}
    </ol>
    <form onSubmit={(event) => void submit(event)} className="space-y-3 rounded-xl border p-4">
      <p className="text-sm font-medium">Cole aqui os dados da sua conta</p>
      {fields.map((field) => <div key={field.key} className="space-y-1">
        <Label htmlFor={`wa-${field.key}`}>{field.label}</Label>
        <Input id={`wa-${field.key}`} value={form[field.key]} placeholder={field.hint} autoComplete="off" spellCheck={false}
          type={field.secret ? "password" : "text"} inputMode={field.numeric ? "numeric" : undefined}
          onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))} />
      </div>)}
      <p className="text-xs text-muted-foreground">Os dados ficam criptografados e servem só para a Kiara ler e responder as conversas do seu número.</p>
      <Button type="submit" className="w-full" disabled={!ready || sending || disabled}>
        {sending ? <LoaderCircle className="animate-spin" /> : <ShieldCheck />}{sending ? "Conferindo com a Meta…" : "Conectar meu WhatsApp oficial"}</Button>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </form>
  </div>
}

/** Official WhatsApp (Meta Cloud API): the client's own Meta app (default) or, when Kiara's app exists, Meta's signup window. */
export function WhatsAppOfficialPanel() {
  const [status, setStatus] = useState<OfficialStatus | null>(null)
  const [busy, setBusy] = useState<"" | "checking" | "connecting" | "disconnecting">("checking")
  const [error, setError] = useState("")
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  const session = useRef<SessionInfo | null>(null)

  const refresh = useCallback(async () => {
    setBusy("checking"); setError("")
    try { setStatus(await officialRequest<OfficialStatus>("status")) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível verificar.") }
    finally { setBusy("") }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial probe of an external system
    void refresh()
    // Meta's window reports the account and number the client picked through postMessage.
    function onMessage(event: MessageEvent) {
      if (!event.origin.endsWith("facebook.com")) return
      try {
        const data = typeof event.data === "string" ? JSON.parse(event.data) : event.data
        if (data?.type !== "WA_EMBEDDED_SIGNUP") return
        if (String(data.event).startsWith("FINISH") && data.data?.waba_id) {
          session.current = { waba_id: String(data.data.waba_id), phone_number_id: String(data.data.phone_number_id ?? "") }
        } else if (data.event === "CANCEL") {
          setError("Cadastro na Meta interrompido. Você pode continuar de onde parou clicando no botão de novo.")
        } else if (data.event === "ERROR") {
          setError(`A Meta informou um erro: ${String(data.data?.error_message ?? "tente novamente")}`)
        }
      } catch { /* other facebook.com messages are not JSON */ }
    }
    window.addEventListener("message", onMessage)
    return () => window.removeEventListener("message", onMessage)
  }, [refresh])

  async function connect() {
    if (!status?.platform_ready) return
    setBusy("connecting"); setError(""); session.current = null
    try {
      const FB = await loadFacebookSdk(status.app_id, status.graph_version)
      const code = await new Promise<string>((resolve, reject) => {
        FB.login((response) => {
          const value = response.authResponse?.code
          if (value) resolve(value)
          else reject(new Error("O cadastro na Meta não foi concluído."))
        }, { config_id: status.config_id, response_type: "code", override_default_response_type: true, extras: { setup: {} } })
      })
      // The account details arrive by postMessage around the same moment; the code lives only ~30 s.
      // (Filled by the message listener while we wait, hence the explicit re-read.)
      const picked = () => session.current as SessionInfo | null
      for (let wait = 0; !picked() && wait < 20; wait += 1) await new Promise((resolve) => setTimeout(resolve, 150))
      const account = picked()
      if (!account?.phone_number_id) throw new Error("Escolha ou cadastre um número de telefone na janela da Meta para usar a API oficial.")
      await officialRequest("connect", { code, waba_id: account.waba_id, phone_number_id: account.phone_number_id })
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível conectar.")
    } finally { setBusy("") }
  }

  async function disconnect() {
    setBusy("disconnecting"); setError(""); setConfirmDisconnect(false)
    try { await officialRequest("disconnect"); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível desconectar.") }
    finally { setBusy("") }
  }

  const quality = qualityLabels[status?.quality_rating ?? ""]
  return <div className="space-y-4">
    {status?.connected ? <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4" role="status">
        <BadgeCheck className="mt-0.5 size-5 shrink-0 text-emerald-400" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">WhatsApp oficial conectado</p>
          <p className="text-sm text-muted-foreground">{status.verified_name || "Sua empresa"} · {status.display_phone_number || "número cadastrado"}</p>
          {quality ? <p className={cn("mt-1 text-xs", quality.tone)}>{quality.label} na Meta</p> : null}
        </div>
      </div>
      {status.registered === false ? <p className="flex items-start gap-2 text-sm text-amber-400"><CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />O número ainda não foi ativado para envio. Confira o número no WhatsApp Manager e reconecte.</p> : null}
      <div className="rounded-xl border p-4 text-sm">
        <p className="flex items-center gap-2 font-medium"><CreditCard className="size-4 text-primary" aria-hidden="true" />Forma de pagamento</p>
        <p className="mt-1 text-muted-foreground">Para enviar mensagens, cadastre seu cartão na Meta. A cobrança das conversas é feita pela Meta direto para você.</p>
        <Button asChild variant="outline" size="sm" className="mt-3"><a href={status.manager_url} target="_blank" rel="noopener noreferrer">Abrir WhatsApp Manager<ExternalLink /></a></Button>
      </div>
      {status.webhook_url && status.verify_token ? <details className="rounded-xl border p-4 text-sm">
        <summary className="cursor-pointer font-medium">Se as mensagens não chegarem na Kiara</summary>
        <p className="mt-2 text-muted-foreground">No seu app da Meta, abra WhatsApp → Configuração, clique em Editar no Webhook, cole os dois valores abaixo e ative o campo messages.</p>
        <div className="mt-3 space-y-3"><CopyField label="URL de retorno" value={status.webhook_url} /><CopyField label="Token de verificação" value={status.verify_token} /></div>
      </details> : null}
      {confirmDisconnect
        ? <div className="flex flex-wrap items-center gap-2 rounded-xl border border-destructive/30 p-3 text-sm"><span className="flex-1">Desconectar a API oficial da Kiara? Sua conta na Meta continua existindo.</span><Button type="button" size="sm" variant="destructive" onClick={() => void disconnect()}>Desconectar</Button><Button type="button" size="sm" variant="ghost" onClick={() => setConfirmDisconnect(false)}>Cancelar</Button></div>
        : <Button type="button" variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setConfirmDisconnect(true)} disabled={Boolean(busy)}>{busy === "disconnecting" ? <LoaderCircle className="animate-spin" /> : <Unplug />}Desconectar</Button>}
    </div> : <div className="space-y-4">
      <ul className="space-y-2 text-sm text-muted-foreground">
        <li className="flex gap-2"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-400" aria-hidden="true" />Conexão direta com a plataforma oficial da Meta, na sua própria conta.</li>
        <li className="flex gap-2"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-400" aria-hidden="true" />Você cria tudo na sua própria conta da Meta. A Kiara só lê e responde as conversas.</li>
        <li className="flex gap-2"><CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-400" aria-hidden="true" />O número usado na API oficial sai do aplicativo do WhatsApp no celular. Use um número dedicado ao atendimento.</li>
        <li className="flex gap-2"><CreditCard className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />Os custos das mensagens ficam com você, cobrados pela Meta no seu cartão, pela tabela oficial dela.</li>
      </ul>
      {status ? <ManualConnect onConnected={refresh} disabled={Boolean(busy)} /> : null}
      {status?.platform_ready ? <details className="rounded-xl border p-4 text-sm">
        <summary className="cursor-pointer font-medium">Ou conecte pela janela da Meta</summary>
        <div className="mt-3 space-y-2"><Button type="button" size="lg" className="w-full bg-[#1877F2] text-white hover:bg-[#1877F2]/90" onClick={() => void connect()} disabled={Boolean(busy) || !status}>
          {busy === "connecting" ? <LoaderCircle className="animate-spin" /> : <svg viewBox="0 0 24 24" className="size-5 fill-current" aria-hidden="true"><path d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.04V9.41c0-3.02 1.8-4.7 4.54-4.7 1.31 0 2.68.24 2.68.24v2.97h-1.5c-1.5 0-1.96.93-1.96 1.89v2.26h3.33l-.53 3.49h-2.8V24C19.62 23.1 24 18.1 24 12.07" /></svg>}
          {busy === "connecting" ? "Conectando com a Meta…" : "Conectar com a Meta"}</Button>
          <p className="text-xs text-muted-foreground">A janela da Meta abre por cima desta página. Se ela não aparecer, permita pop-ups para este site.</p></div>
      </details> : null}
    </div>}
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {busy === "checking" && !status ? <p className="flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" />Verificando…</p> : null}
    {status && !busy ? <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground" aria-label="Atualizar" onClick={() => void refresh()}><RefreshCw /></Button> : null}
  </div>
}
