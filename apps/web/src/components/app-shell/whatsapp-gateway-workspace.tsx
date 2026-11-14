"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { CheckCircle2, LoaderCircle, RefreshCw, Smartphone } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { connectWhatsAppWeb, whatsappWebRequest, type WhatsAppEvents } from "@/lib/whatsapp-web-client"

const BRIDGE_URL = "http://127.0.0.1:3009"
const PAIRING_TIMEOUT_MS = 3 * 60_000

type ServerStatus = { connected: boolean; state: string; phone: string }
type ConnectResult = ServerStatus & { qr: string }
export type WhatsAppSyncResult = ServerStatus & { conversations: number; messages: number; skipped: number }

/** WhatsApp on the always-on Debian server (OpenWA behind the Kiara gateway), through the Kiara API. */
async function serverRequest<T>(action: "status" | "connect" | "sync", signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(action === "sync" ? 65_000 : 35_000)
  let response: Response
  try {
    response = await fetch(`/api/whatsapp-server/${action}`, { method: "POST", cache: "no-store", signal: signal ? AbortSignal.any([signal, timeout]) : timeout })
  } catch {
    throw new Error("Não foi possível falar com o servidor da Kiara. Verifique a internet.")
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof payload?.error?.message === "string" ? payload.error.message : "Não foi possível acessar o WhatsApp da Kiara.")
  if (typeof payload?.connected !== "boolean" || typeof payload?.state !== "string") throw new Error("O servidor retornou um estado inválido. Tente novamente.")
  if (action === "connect" && (typeof payload.qr !== "string" || (payload.qr && !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(payload.qr)))) {
    throw new Error("O servidor retornou um QR inválido. Tente novamente.")
  }
  return payload as T
}

/** Copies the recent WhatsApp conversations of the server session into the inbox (read-only, nothing is sent). */
export function syncWhatsAppConversations(signal?: AbortSignal) {
  return serverRequest<WhatsAppSyncResult>("sync", signal)
}

async function getSiteAccessToken(signal?: AbortSignal) {
  const response = await fetch("/api/whatsapp-web/session", { method: "POST", cache: "no-store", signal })
  const payload = await response.json().catch(() => null)
  if (!response.ok || typeof payload?.access_token !== "string") {
    throw new Error(response.status === 401
      ? "Entre novamente na Kiara para acessar o WhatsApp."
      : "Sua conta não tem permissão para conectar o WhatsApp (owner ou admin).")
  }
  return payload.access_token as string
}

async function bridgeRequest<T>(action: "status" | "connect" | "analyze" | "scan", signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(action === "scan" ? 900_000 : action === "analyze" ? 135_000 : 30_000)
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
    throw new Error("O serviço do WhatsApp da Kiara não está ativo neste computador.")
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof payload?.error === "string" ? payload.error : "Não foi possível acessar o WhatsApp.")
  if (action === "status" && (typeof payload?.connected !== "boolean" || typeof payload?.state !== "string" || typeof payload?.phone !== "string" || typeof payload?.model !== "string")) {
    throw new Error("O serviço retornou um estado inválido. Atualize e tente novamente.")
  }
  if (action === "connect" && (typeof payload?.connected !== "boolean" || typeof payload?.state !== "string" || typeof payload?.qr !== "string" || (payload.qr && !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(payload.qr)))) {
    throw new Error("O serviço retornou um QR inválido. Tente novamente.")
  }
  if (action === "analyze" && (typeof payload?.summary !== "string" || !payload.summary.trim() || typeof payload?.phone !== "string" || !Number.isInteger(payload?.messages_analyzed) || payload.messages_analyzed < 0)) {
    throw new Error("A análise não retornou um resumo válido. Tente novamente.")
  }
  if (action === "scan" && (!Array.isArray(payload?.leads) || !Number.isInteger(payload?.scanned) || !Number.isInteger(payload?.skipped))) {
    throw new Error("A análise das conversas não retornou um resultado válido.")
  }
  return payload as T
}

export type WhatsAppScanResult = { leads: { phone: string; name: string; stage: string; summary: string; next_action: string; confidence: number }[]; scanned: number; skipped: number }

/** Reads and understands the most recent chats of the QR-connected session (read-only, nothing is sent). */
export function scanWhatsAppConversations() {
  return bridgeRequest<WhatsAppScanResult>("scan")
}

const stateLabels: Record<string, string> = {
  ready: "WhatsApp conectado", qr_ready: "Escaneie o QR Code", initializing: "Preparando a conexão…",
  authenticating: "Confirmando no celular…", created: "Desconectado", disconnected: "Desconectado", unknown: "Verificando…",
  failed: "A conexão falhou", action_required: "O WhatsApp pediu uma ação no celular", not_created: "Desconectado",
}

/** Connects WhatsApp by QR Code on the Kiara server (on 24h), like WhatsApp Web, without any extension. */
export function WhatsAppConnectionPanel({ onConnected }: { onConnected?: () => void } = {}) {
  const [status, setStatus] = useState<ServerStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [pairing, setPairing] = useState<ConnectResult | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState("")
  const pollRef = useRef<AbortController | null>(null)

  const check = useCallback(async (signal?: AbortSignal) => {
    setChecking(true); setError("")
    try { setStatus(await serverRequest<ServerStatus>("status", signal)) }
    catch (reason) { if (!signal?.aborted) { setStatus(null); setError(reason instanceof Error ? reason.message : "Não foi possível verificar a conexão.") } }
    finally { if (!signal?.aborted) setChecking(false) }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    // Initial status probe of the WhatsApp session.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void check(controller.signal)
    return () => { controller.abort(); pollRef.current?.abort() }
  }, [check])

  async function connect() {
    pollRef.current?.abort()
    const controller = new AbortController()
    pollRef.current = controller
    setConnecting(true); setError(""); setPairing(null)
    const deadline = Date.now() + PAIRING_TIMEOUT_MS
    try {
      // Poll the session: it starts once, then shows each fresh QR until the phone confirms.
      while (!controller.signal.aborted && Date.now() < deadline) {
        const result = await serverRequest<ConnectResult>("connect", controller.signal)
        if (controller.signal.aborted) return
        setPairing(result)
        if (result.connected) { await check(); onConnected?.(); return }
        if (result.state === "failed" || result.state === "action_required") throw new Error(stateLabels[result.state])
        await new Promise((resolve) => setTimeout(resolve, 3000))
      }
      if (!controller.signal.aborted) setError("O QR Code expirou. Clique em Conectar para gerar outro.")
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Não foi possível conectar.")
    } finally { if (!controller.signal.aborted) setConnecting(false) }
  }

  const connected = Boolean(status?.connected || pairing?.connected)
  const state = pairing?.state ?? status?.state ?? ""
  const headline = checking && !pairing ? "Verificando…" : connected ? "WhatsApp conectado" : stateLabels[state] ?? "Desconectado"

  return <div className="space-y-5">
    <div className="flex items-center gap-3 rounded-xl border p-4">
      <span className={cn("size-2.5 shrink-0 rounded-full", connected ? "bg-emerald-400" : checking || connecting ? "bg-amber-400" : "bg-muted-foreground")} aria-hidden="true" />
      <div className="min-w-0 flex-1" role="status">
        <p className="font-medium">{headline}</p>
        <p className="text-sm text-muted-foreground">{error || (connected ? `Sessão ativa no servidor da Kiara${status?.phone ? ` (${status.phone})` : ""}. As conversas aparecem na caixa de entrada.` : "Conecte uma vez pelo celular; a sessão fica salva no servidor, mesmo com o computador desligado.")}</p>
      </div>
      <Button type="button" variant="outline" size="icon" aria-label="Atualizar conexão" onClick={() => void check()} disabled={checking || connecting}>{checking ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}</Button>
    </div>

    {connected ? <p className="flex items-center gap-2 text-sm text-emerald-400"><CheckCircle2 className="size-4" aria-hidden="true" />Tudo certo. Você pode fechar esta janela.</p>
      : pairing?.qr ? <div className="flex flex-col items-center gap-4 rounded-xl border bg-white p-4 sm:flex-row sm:items-start">
        {/* eslint-disable-next-line @next/next/no-img-element -- data URL from the server session, not an optimizable asset */}
        <img src={pairing.qr} alt="QR Code para conectar o WhatsApp" className="size-52 shrink-0" />
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-neutral-800">
          <li>Abra o WhatsApp no celular.</li>
          <li>Toque em <strong>Mais opções</strong> ou <strong>Configurações</strong> e em <strong>Aparelhos conectados</strong>.</li>
          <li>Toque em <strong>Conectar um aparelho</strong> e aponte para este QR Code.</li>
        </ol>
      </div>
      : <Button type="button" className="w-full" size="lg" onClick={() => void connect()} disabled={connecting || checking}>{connecting ? <LoaderCircle className="animate-spin" /> : <Smartphone />}{connecting ? "Gerando QR Code…" : "Conectar WhatsApp"}</Button>}

    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer">Detalhes técnicos</summary>
      <div className="mt-2 space-y-2">
        <p>A sessão é mantida pelo OpenWA no servidor da Kiara (ligado 24 h) e acessada pela API por um gateway protegido.</p>
        <p>Conectar exige conta owner/admin. A sincronização só lê conversas individuais recentes; nada é enviado.</p>
      </div>
    </details>
  </div>
}

/** Optional alternative: WhatsApp Web open in this Chrome, read through the Kiara extension and the local executor. */
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
  return <div className="space-y-3">
    <p className="text-sm text-muted-foreground">{connecting ? "Entre no WhatsApp na guia aberta e leia o QR Code com o celular. A Kiara aguarda a confirmação por até 3 minutos." : "Usa o WhatsApp Web aberto neste Chrome, por meio da extensão Kiara WhatsApp."}</p>
    <details className="rounded-lg border p-3 text-sm">
      <summary className="cursor-pointer font-medium">Instalar ou atualizar a extensão Kiara</summary>
      <ol className="mt-3 list-decimal space-y-2 pl-5 text-muted-foreground">
        <li><a className="font-medium text-primary underline" href="/downloads/kiara-whatsapp-extension.zip" download>Baixe a extensão</a> e extraia o ZIP em uma pasta fixa.</li>
        <li>No Chrome, abra <code>chrome://extensions</code> e habilite o Modo do desenvolvedor.</li>
        <li>Clique em Carregar sem compactação e selecione a pasta extraída. Se já estiver instalada, atualize os arquivos e clique em Recarregar.</li>
        <li>Atualize as guias da Kiara e do WhatsApp Web e tente conectar novamente.</li>
      </ol>
    </details>
    <div className="flex flex-wrap items-center gap-3">
      <span className="inline-flex items-center gap-1.5 text-sm"><span className={cn("size-2 rounded-full", online ? "bg-emerald-400" : "bg-muted-foreground")} aria-hidden="true" />{checking ? "Verificando…" : online ? "Extensão conectada" : "Extensão não conectada"}</span>
      <Button type="button" size="sm" variant="outline" onClick={() => void connect()} disabled={connecting}>{connecting ? <LoaderCircle className="animate-spin" /> : null}Conectar pela extensão</Button>
    </div>
    {error ? <p className="text-sm text-destructive">{error}</p> : null}
  </div>
}
