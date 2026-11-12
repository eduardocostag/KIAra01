"use client"

import Link from "next/link"
import { useCallback, useEffect, useRef, useState } from "react"
import { AlertCircle, ArrowRight, ArrowUpRight, CheckCircle2, ChevronDown, CircleHelp, Cpu, FileText, Link2, LoaderCircle, LockKeyhole, MessageCircle, Monitor, RefreshCw, ScanLine, Settings2, ShieldCheck, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import styles from "./whatsapp-workspace.module.css"

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
  const timeout = AbortSignal.timeout(action === "analyze" ? 135_000 : 15_000)
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  const token = await getSiteAccessToken(requestSignal)
  let response: Response
  try {
    response = await fetch(`${BRIDGE_URL}/api/${action}`, {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ action }),
      signal: requestSignal,
    })
  } catch {
    throw new Error("Ponte local indisponível. Inicie o serviço WhatsApp da Kiara neste computador.")
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof payload?.error === "string" ? payload.error : "Não foi possível acessar a conversa.")
  }
  if (action === "status" && (typeof payload?.connected !== "boolean" || typeof payload?.phone !== "string" || typeof payload?.model !== "string")) {
    throw new Error("A ponte local retornou um estado inválido. Atualize a conexão e verifique o serviço neste computador.")
  }
  if (action === "analyze" && (typeof payload?.summary !== "string" || !payload.summary.trim() || typeof payload?.phone !== "string" || !Number.isInteger(payload?.messages_analyzed) || payload.messages_analyzed < 0)) {
    throw new Error("A análise não retornou um resumo válido. Verifique o modelo local e tente novamente.")
  }
  return payload as T
}

export function WhatsAppGatewayWorkspace() {
  const [status, setStatus] = useState<BridgeStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState("")
  const settingsRef = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    function revealSettings() {
      if (window.location.hash === "#configuracoes" && settingsRef.current) settingsRef.current.open = true
    }
    revealSettings()
    window.addEventListener("hashchange", revealSettings)
    return () => window.removeEventListener("hashchange", revealSettings)
  }, [])

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

  const connected = Boolean(status?.connected)
  const connectionLabel = checking ? "Verificando conexão" : connected ? "WhatsApp conectado" : "Conexão pendente"

  return <section className={styles.workspace} aria-labelledby="wa-gateway-heading">
    <header className={styles.pageHeader}>
      <div className={styles.headingGroup}>
        <span className={styles.moduleIcon}><MessageCircle aria-hidden="true" /></span>
        <div><p className={styles.eyebrow}>Seu espaço de conversas</p><h1 id="wa-gateway-heading">Central do WhatsApp</h1><p>Conecte seu WhatsApp e transforme conversas em contexto para o atendimento.</p></div>
      </div>
      <div className={styles.headerActions}>
        {connected && <Button type="button" className={styles.primaryButton} aria-controls="analise" onClick={() => void analyze()} disabled={checking || analyzing}>{analyzing ? <LoaderCircle className="animate-spin motion-reduce:animate-none" /> : <Sparkles />}Analisar agora</Button>}
        <Button type="button" variant="outline" className={styles.secondaryButton} onClick={() => void checkStatus()} disabled={checking || analyzing}><RefreshCw className={checking ? "animate-spin motion-reduce:animate-none" : ""} />Atualizar conexão</Button>
      </div>
    </header>

    <div className={styles.statusStrip} aria-label="Estado da operação">
      <div><span className={styles.statusIcon}><Link2 aria-hidden="true" /></span><div><p>Conexão</p><strong className={connected && !checking ? styles.successText : ""}>{connectionLabel}</strong></div></div>
      <div><span className={styles.statusIcon}><MessageCircle aria-hidden="true" /></span><div><p>Contato autorizado</p><strong>{status?.phone || (checking ? "Consultando…" : "Ainda não identificado")}</strong></div></div>
      <div><span className={styles.statusIcon}><Cpu aria-hidden="true" /></span><div><p>Modelo de análise</p><strong>{status?.model || (checking ? "Consultando…" : "Aguardando conexão")}</strong></div></div>
    </div>

    {error ? <p className={styles.error} role="alert"><AlertCircle aria-hidden="true" /><span>{error}</span></p> : null}

    <div className={styles.workGrid}>
      <div className={styles.mainColumn}>
        <section id="conexao" className={`${styles.panel} ${styles.connectionPanel}`} aria-labelledby="wa-connection-heading">
          <div className={styles.panelHeader}><div className={styles.sectionIdentity}><span className={styles.greenIcon}><ScanLine aria-hidden="true" /></span><div><p className={styles.eyebrow}>01 · Conectar</p><h2 id="wa-connection-heading">Sua sessão, neste computador</h2></div></div><span className={connected && !checking ? styles.connectedBadge : styles.pendingBadge}>{checking ? <LoaderCircle className="animate-spin motion-reduce:animate-none" /> : connected ? <CheckCircle2 /> : <Monitor />}{checking ? "Verificando" : connected ? "Conectado" : "Aguardando"}</span></div>
          <p className={styles.description}>Acesse sua sessão local para analisar o contato autorizado. A conexão usa sua conta Kiara e mantém o WhatsApp neste computador.</p>
          <ol className={styles.connectionSteps}>
            <li><span>1</span><div><strong>Abra sua sessão do WhatsApp</strong><p>Inicie o OpenWA e conclua o login por QR Code, caso seja solicitado.</p></div></li>
            <li><span>2</span><div><strong>Verifique a conexão com a Kiara</strong><p>Mantenha o serviço local ligado e permita o acesso à rede local no navegador.</p></div></li>
            <li><span>3</span><div><strong>Analise a conversa autorizada</strong><p>O resumo aparece na área de análise, com a quantidade de mensagens realmente analisadas.</p></div></li>
          </ol>
          <div className={styles.panelActions}><Button asChild variant="outline" className={styles.secondaryButton}><a href="http://127.0.0.1:3006" target="_blank" rel="noopener noreferrer">Abrir WhatsApp local<ArrowUpRight /></a></Button><a className={styles.textLink} href="#configuracoes">Preciso configurar<ArrowRight aria-hidden="true" /></a></div>
          <div className={styles.connectionFeedback} role="status" aria-live="polite">{checking ? <LoaderCircle className="animate-spin motion-reduce:animate-none" /> : connected ? <CheckCircle2 className={styles.successText} /> : <AlertCircle />}<span>{checking ? "Consultando a ponte local…" : connected ? "Sessão disponível para análise." : "Conecte o WhatsApp e atualize para continuar."}</span></div>
        </section>

        <section id="analise" className={styles.panel} aria-labelledby="wa-analysis-heading" aria-busy={analyzing}>
          <div className={styles.panelHeader}><div className={styles.sectionIdentity}><span className={styles.violetIcon}><Sparkles aria-hidden="true" /></span><div><p className={styles.eyebrow}>02 · Entender</p><h2 id="wa-analysis-heading">Análise da conversa</h2></div></div><span className={styles.quietBadge}><LockKeyhole aria-hidden="true" />Somente leitura</span></div>
          <p className={styles.description}>Gere um resumo do contato configurado no serviço local. Confira as informações antes de decidir o próximo passo.</p>
          {analysis ? <article className={styles.analysisResult} aria-label="Resultado da análise"><div className={styles.resultMeta}><span><CheckCircle2 aria-hidden="true" />Análise concluída</span><span>{analysis.messages_analyzed} mensagens · {analysis.phone}</span></div><div className={styles.summaryText}>{analysis.summary}</div></article> : <div className={styles.emptyAnalysis}><span><FileText aria-hidden="true" /></span><h3>{analyzing ? "Lendo a conversa autorizada…" : "O contexto começa aqui"}</h3><p>{analyzing ? "A IA local está preparando o resumo. Mantenha este computador e a sessão do WhatsApp disponíveis." : "Depois de conectar, inicie a análise para reunir as informações da conversa em um só lugar."}</p></div>}
          <div className={styles.analysisFooter}><Button type="button" className={styles.primaryButton} onClick={() => void analyze()} disabled={!connected || checking || analyzing}>{analyzing ? <LoaderCircle className="animate-spin motion-reduce:animate-none" /> : <Sparkles />}{analyzing ? "Analisando conversa…" : analysis ? "Analisar novamente" : "Analisar conversa autorizada"}</Button><p>O conteúdo analisado não é salvo no site.</p></div>
        </section>
      </div>

      <aside className={styles.sideColumn} aria-label="Orientações e ferramentas do WhatsApp">
        <section className={`${styles.panel} ${styles.guidePanel}`} aria-labelledby="wa-scope-heading"><span className={styles.guideIcon}><ShieldCheck aria-hidden="true" /></span><p className={styles.eyebrow}>Você no controle</p><h2 id="wa-scope-heading">Contexto antes da ação</h2><p>A análise consulta somente o contato autorizado no computador. Iniciar uma análise não envia mensagens.</p><ul className={styles.scopeList}><li><CheckCircle2 aria-hidden="true" />Um contato pré-configurado</li><li><CheckCircle2 aria-hidden="true" />Análise com IA local</li><li><CheckCircle2 aria-hidden="true" />Envio de mensagens desabilitado</li></ul></section>
        <section className={styles.panel} aria-labelledby="wa-tools-heading"><h2 id="wa-tools-heading" className={styles.smallHeading}>Continue seu trabalho</h2><div className={styles.toolLinks}><Link href="/app/whatsapp/automacao"><span><Settings2 aria-hidden="true" /><span><strong>Automação e contatos</strong><small>Configurar o atendimento com executor</small></span></span><ArrowRight aria-hidden="true" /></Link><Link href="/app/inbox"><span><MessageCircle aria-hidden="true" /><span><strong>Caixa de entrada</strong><small>Acompanhar atendimentos</small></span></span><ArrowUpRight aria-hidden="true" /></Link><a href="http://127.0.0.1:20128/home" target="_blank" rel="noopener noreferrer"><span><Cpu aria-hidden="true" /><span><strong>OmniRoute local</strong><small>Gerenciar modelos neste computador</small></span></span><ArrowUpRight aria-hidden="true" /></a></div></section>
        <div className={styles.helpNote}><CircleHelp aria-hidden="true" /><p>O WhatsApp depende da sessão e do serviço local ativos. Fechar o computador interrompe a conexão.</p></div>
      </aside>
    </div>

    <details id="configuracoes" ref={settingsRef} className={styles.settingsPanel}>
      <summary><span><Settings2 aria-hidden="true" /><span><strong>Configuração e diagnóstico</strong><small>Preparar este computador para a análise local</small></span></span><ChevronDown aria-hidden="true" /></summary>
      <div className={styles.settingsBody}>
        <div><h3>Contato autorizado</h3><p>O administrador deve configurar o telefone completo com DDI e DDD em <code>KIARA_WHATSAPP_ANALYSIS_PHONE</code>, no arquivo local <code>.env.local</code>. Esse é o único contato que a ponte pode consultar.</p></div>
        <div><h3>Serviço local</h3><p>Inicie com <code>python scripts/run_whatsapp_local_bridge.py</code>. A ponte usa a sessão OpenWA e o modelo Ollama <code>kiara-stable:latest</code> por padrão, escutando em <code>127.0.0.1:3007</code>.</p></div>
        <div><h3>Permissões de acesso</h3><p>A análise exige uma conta Kiara autenticada com papel owner/admin. Se o navegador solicitar acesso a dispositivos da rede local, permita para conectar este site ao serviço no computador.</p></div>
        <div><h3>Se não conectar</h3><p>Verifique se OpenWA, a ponte e o modelo local estão iniciados. Abra sua sessão do WhatsApp e use Atualizar conexão. A presença da ponte não comprova que o WhatsApp está autenticado.</p></div>
      </div>
    </details>
  </section>
}
