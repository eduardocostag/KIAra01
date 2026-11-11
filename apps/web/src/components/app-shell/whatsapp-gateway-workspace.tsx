"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { AlertCircle, ArrowUpRight, CheckCircle2, LoaderCircle, MessageCircle, RefreshCw, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"

const BRIDGE_URL = "http://127.0.0.1:3007"

type BridgeStatus = { connected: boolean; phone: string; model: string }
type Analysis = { summary: string; messages_analyzed: number; phone: string }

async function getSiteAccessToken(signal?: AbortSignal) {
  const response = await fetch("/api/whatsapp-web/session", {
    method: "POST",
    cache: "no-store",
    signal,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok || typeof payload?.access_token !== "string") {
    throw new Error(response.status === 401
      ? "Entre novamente na Kiara para acessar o WhatsApp."
      : "Sua conta não tem autorização para analisar a conversa.")
  }
  return payload.access_token as string
}

async function bridgeRequest<T>(action: "status" | "analyze", signal?: AbortSignal): Promise<T> {
  const token = await getSiteAccessToken(signal)
  let response: Response
  try {
    response = await fetch(`${BRIDGE_URL}/api/${action}`, {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ action }),
      signal: signal ?? AbortSignal.timeout(action === "analyze" ? 135_000 : 15_000),
    })
  } catch {
    throw new Error("Ponte local indisponível. Inicie o serviço WhatsApp da Kiara neste computador.")
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof payload?.error === "string" ? payload.error : "Não foi possível acessar a conversa.")
  }
  return payload as T
}

export function WhatsAppGatewayWorkspace() {
  const [status, setStatus] = useState<BridgeStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState("")

  const checkStatus = useCallback(async (signal?: AbortSignal) => {
    if (!signal) {
      setChecking(true)
      setError("")
    }
    try {
      const current = await bridgeRequest<BridgeStatus>("status", signal)
      setStatus(current)
    } catch (reason) {
      if (signal?.aborted) return
      setStatus(null)
      setError(reason instanceof Error ? reason.message : "Não foi possível verificar a conexão.")
    } finally {
      if (!signal?.aborted) setChecking(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void bridgeRequest<BridgeStatus>("status", controller.signal)
      .then(setStatus)
      .catch(reason => {
        if (controller.signal.aborted) return
        setStatus(null)
        setError(reason instanceof Error ? reason.message : "Não foi possível verificar a conexão.")
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false)
      })
    return () => controller.abort()
  }, [])

  async function analyze() {
    setAnalyzing(true)
    setError("")
    setAnalysis(null)
    try {
      setAnalysis(await bridgeRequest<Analysis>("analyze"))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível analisar a conversa.")
    } finally {
      setAnalyzing(false)
    }
  }

  return <section className="mx-auto w-full max-w-4xl space-y-5" aria-labelledby="wa-gateway-heading">
    <header>
      <h1 id="wa-gateway-heading" className="text-2xl font-semibold">WhatsApp</h1>
      <p className="mt-2 text-sm text-muted-foreground">Analise a conversa de um único contato com a IA local da Kiara. Sem extensão e sem enviar mensagens.</p>
    </header>

    <div className="rounded-2xl border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 font-semibold"><MessageCircle className="size-4" />Conexão local e privada</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">O WhatsApp e o modelo ficam neste computador. O site solicita uma autorização curta à sua conta e a ponte local permite somente consultar o contato pré-configurado.</p>
        </div>
        <Button asChild variant="outline"><a href="http://127.0.0.1:3006" target="_blank" rel="noopener noreferrer">Abrir OpenWA<ArrowUpRight className="size-4" /></a></Button>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <div className="flex items-center gap-2 text-sm" role="status" aria-live="polite">
          {checking ? <LoaderCircle className="size-4 animate-spin text-muted-foreground" />
            : status?.connected ? <CheckCircle2 className="size-4 text-emerald-600" />
              : <AlertCircle className="size-4 text-amber-600" />}
          <span>{checking ? "Verificando conexão local…" : status?.connected ? `WhatsApp conectado · ${status.phone}` : "WhatsApp ou ponte local desconectados"}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => void checkStatus()} disabled={checking || analyzing}>
          <RefreshCw className="size-4" />Verificar
        </Button>
      </div>

      {error && <p className="mt-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p>}

      <div className="mt-5">
        <Button onClick={() => void analyze()} disabled={!status?.connected || checking || analyzing}>
          {analyzing ? <><LoaderCircle className="size-4 animate-spin" />Analisando conversa…</> : "Analisar conversa autorizada"}
        </Button>
      </div>
    </div>

    {analysis && <article className="rounded-2xl border bg-card p-5 sm:p-6" aria-labelledby="wa-analysis-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="wa-analysis-heading" className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-emerald-600" />Resumo da conversa</h2>
        <span className="text-xs text-muted-foreground">{analysis.phone} · {analysis.messages_analyzed} mensagens</span>
      </div>
      <div className="mt-4 whitespace-pre-wrap text-sm leading-6">{analysis.summary}</div>
      <p className="mt-4 border-t pt-3 text-xs text-muted-foreground">Análise somente leitura. Nenhuma mensagem foi enviada; o conteúdo não é salvo no site.</p>
    </article>}

    <div className="flex flex-wrap gap-3">
      <Button asChild variant="outline"><Link href="/app/inbox">Caixa de entrada</Link></Button>
      <Button asChild variant="ghost"><a href="http://127.0.0.1:20128/home" target="_blank" rel="noopener noreferrer">OmniRoute local<ArrowUpRight className="size-4" /></a></Button>
    </div>

    <details className="rounded-2xl border bg-card">
      <summary className="cursor-pointer p-5 text-sm font-medium">Configurar análise neste computador</summary>
      <div className="space-y-3 border-t p-5 text-sm text-muted-foreground">
        <p>Adicione ao arquivo local ignorado pelo Git <code>.env.local</code> o telefone completo com DDI e DDD, por exemplo <code>+5511999999999</code>, em <code>KIARA_WHATSAPP_ANALYSIS_PHONE</code>. Esse é o único contato que a ponte pode consultar.</p>
        <p>Inicie a ponte local com <code>python scripts/run_whatsapp_local_bridge.py</code>. Ela usa a sessão OpenWA e o modelo Ollama <code>kiara-stable:latest</code> por padrão. A ponte escuta somente em <code>127.0.0.1:3007</code>.</p>
        <p>Acesso restrito a usuários Kiara autenticados com papel owner/admin. Análise, respostas automáticas e prospecção não habilitam envio; esta ponte não tem rota de envio nem lista contatos.</p>
        <p>O navegador pode pedir permissão para a Kiara acessar dispositivos na rede local. Autorize para permitir que o site hospedado fale com esta ponte neste computador.</p>
      </div>
    </details>
  </section>
}
