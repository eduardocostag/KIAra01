"use client"

import { useCallback, useEffect, useState } from "react"
import { ArrowUpRight, LoaderCircle, RefreshCw, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { connectWhatsAppWeb, whatsappWebRequest, type WhatsAppEvents } from "@/lib/whatsapp-web-client"

const BRIDGE_URL = "http://127.0.0.1:3007"

type BridgeStatus = { connected: boolean; phone: string; model: string }
type Analysis = { summary: string; messages_analyzed: number; phone: string }

async function getSiteAccessToken(signal?: AbortSignal) {
  const response = await fetch("/api/whatsapp-web/session", { method: "POST", cache: "no-store", signal })
  const payload = await response.json().catch(() => null)
  if (!response.ok || typeof payload?.access_token !== "string") {
    throw new Error(response.status === 401
      ? "Entre novamente na Kiara para acessar o WhatsApp."
      : "Sua conta não tem autorização para analisar a conversa.")
  }
  return payload.access_token as string
}

async function bridgeRequest<T>(action: "status" | "analyze", signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(action === "analyze" ? 135_000 : 15_000)
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  const token = await getSiteAccessToken(requestSignal)
  let response: Response
  try {
    response = await fetch(`${BRIDGE_URL}/api/${action}`, {
      method: "POST", mode: "cors", credentials: "omit", cache: "no-store",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ action }), signal: requestSignal,
    })
  } catch {
    throw new Error("O serviço do WhatsApp não está ativo neste computador.")
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof payload?.error === "string" ? payload.error : "Não foi possível acessar a conversa.")
  if (action === "status" && (typeof payload?.connected !== "boolean" || typeof payload?.phone !== "string" || typeof payload?.model !== "string")) {
    throw new Error("O serviço retornou um estado inválido. Atualize e tente novamente.")
  }
  if (action === "analyze" && (typeof payload?.summary !== "string" || !payload.summary.trim() || typeof payload?.phone !== "string" || !Number.isInteger(payload?.messages_analyzed) || payload.messages_analyzed < 0)) {
    throw new Error("A análise não retornou um resumo válido. Tente novamente.")
  }
  return payload as T
}

/** WhatsApp Web logged in this Chrome, reached through the Kiara extension and the local executor. */
export function WhatsAppWebConnectionPanel() {
  const [events, setEvents] = useState<WhatsAppEvents | null>(null)
  const [checking, setChecking] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState("")

  const check = useCallback(async (signal?: AbortSignal) => {
    setChecking(true)
    try { setEvents(await whatsappWebRequest<WhatsAppEvents>("events", signal ? { signal } : undefined)); setError("") }
    catch (reason) { if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Não foi possível verificar a conexão.") }
    finally { if (!signal?.aborted) setChecking(false) }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    // Initial status probe of the executor heartbeat.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void check(controller.signal)
    return () => controller.abort()
  }, [check])

  async function connect() {
    setConnecting(true); setError("")
    try { await connectWhatsAppWeb(); await check() }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível conectar.") }
    finally { setConnecting(false) }
  }

  const online = Boolean(events?.online)
  return <div className="space-y-5">
    <div className="flex items-center gap-3 rounded-xl border p-4">
      <span className={cn("size-2.5 shrink-0 rounded-full", checking || connecting ? "bg-amber-400" : online ? "bg-emerald-400" : "bg-muted-foreground")} aria-hidden="true" />
      <div className="min-w-0 flex-1" role="status">
        <p className="font-medium">{connecting ? "Conectando…" : checking ? "Verificando…" : online ? "WhatsApp Web conectado" : "WhatsApp Web desconectado"}</p>
        <p className="text-sm text-muted-foreground">{error || (online ? "A Kiara pode identificar, entender, prospectar e responder pelos contatos autorizados." : "Abra o WhatsApp Web logado no Chrome e clique em Conectar.")}</p>
      </div>
      <Button type="button" variant="outline" size="icon" aria-label="Atualizar conexão" onClick={() => void check()} disabled={checking || connecting}>{checking ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}</Button>
    </div>
    <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
      <li>Faça login no <a href="https://web.whatsapp.com" target="_blank" rel="noopener noreferrer" className="text-foreground underline">WhatsApp Web</a> neste Chrome.</li>
      <li>Deixe a extensão Kiara WhatsApp ativa.</li>
      <li>Clique em Conectar e mantenha as duas abas abertas.</li>
    </ol>
    <div className="flex flex-wrap gap-2">
      <Button type="button" onClick={() => void connect()} disabled={connecting}>{connecting ? <LoaderCircle className="animate-spin" /> : null}Conectar</Button>
      <Button asChild variant="outline"><a href="/app/whatsapp/automacao">Configurar o que a Kiara faz</a></Button>
    </div>
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer">Detalhes técnicos</summary>
      <div className="mt-2 space-y-2">
        <p>Extensão: pasta <code>extensions/kiara-whatsapp</code>, carregada no Chrome em modo de desenvolvedor.</p>
        <p>Executor: <code>scripts/launch_whatsapp_executor.ps1</code>. Análise e respostas usam o modelo do Ollama configurado em <code>KIARA_WHATSAPP_OLLAMA_MODEL</code>.</p>
        <p>{events?.last_heartbeat_at ? `Último sinal do executor: ${new Date(events.last_heartbeat_at).toLocaleString("pt-BR")}.` : "Nenhum sinal do executor ainda."} Conectado aqui não confirma o login no WhatsApp Web.</p>
      </div>
    </details>
  </div>
}

/** Connection state of the WhatsApp session plus the read-only analysis of the authorized contact. */
export function WhatsAppConnectionPanel() {
  const [status, setStatus] = useState<BridgeStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState("")

  const check = useCallback(async (signal?: AbortSignal) => {
    setChecking(true); setError("")
    try { setStatus(await bridgeRequest<BridgeStatus>("status", signal)) }
    catch (reason) { if (!signal?.aborted) { setStatus(null); setError(reason instanceof Error ? reason.message : "Não foi possível verificar a conexão.") } }
    finally { if (!signal?.aborted) setChecking(false) }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    // Initial status probe of the local session.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void check(controller.signal)
    return () => controller.abort()
  }, [check])

  async function analyze() {
    setAnalyzing(true); setError(""); setAnalysis(null)
    try { setAnalysis(await bridgeRequest<Analysis>("analyze")) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível analisar a conversa.") }
    finally { setAnalyzing(false) }
  }

  const connected = Boolean(status?.connected)
  return <div className="space-y-5">
    <div className="flex items-center gap-3 rounded-xl border p-4">
      <span className={cn("size-2.5 shrink-0 rounded-full", checking ? "bg-amber-400" : connected ? "bg-emerald-400" : "bg-muted-foreground")} aria-hidden="true" />
      <div className="min-w-0 flex-1" role="status">
        <p className="font-medium">{checking ? "Verificando…" : connected ? "WhatsApp conectado" : "WhatsApp desconectado"}</p>
        <p className="truncate text-sm text-muted-foreground">{status?.phone ? `Contato autorizado: ${status.phone}` : error || "Abra a sessão do WhatsApp e atualize."}</p>
      </div>
      <Button type="button" variant="outline" size="icon" aria-label="Atualizar conexão" onClick={() => void check()} disabled={checking || analyzing}>{checking ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}</Button>
    </div>

    <div className="flex flex-wrap gap-2">
      <Button type="button" onClick={() => void analyze()} disabled={!connected || checking || analyzing}>{analyzing ? <LoaderCircle className="animate-spin" /> : <Sparkles />}{analyzing ? "Analisando…" : "Resumir conversa autorizada"}</Button>
      <Button asChild variant="outline"><a href="http://127.0.0.1:3006" target="_blank" rel="noopener noreferrer">Abrir sessão do WhatsApp<ArrowUpRight /></a></Button>
    </div>

    {error && status ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {analysis ? <article className="rounded-xl border bg-muted/30 p-4" aria-label="Resumo da conversa">
      <p className="text-xs text-muted-foreground">{analysis.messages_analyzed} mensagens · {analysis.phone} · não salvo no site</p>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{analysis.summary}</p>
    </article> : null}

    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer">Detalhes técnicos</summary>
      <div className="mt-2 space-y-2">
        <p>Contato autorizado: <code>KIARA_WHATSAPP_ANALYSIS_PHONE</code> no <code>.env.local</code>.</p>
        <p>Serviço: <code>python scripts/run_whatsapp_local_bridge.py</code> (porta 3007), usando a sessão OpenWA (porta 3006) e o Ollama local.</p>
        <p>Exige conta owner/admin. O navegador pode pedir acesso à rede local.</p>
      </div>
    </details>
  </div>
}
