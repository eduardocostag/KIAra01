"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { AtSign, CheckCircle2, ClipboardPaste, Database, Download, ExternalLink, ListChecks, Loader2, MessageCircleMore, Play, Radar, RefreshCw, ScanSearch, Search, ShieldCheck, Sparkles, UsersRound } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import styles from "@/app/(app)/app/concorrencia/competition.module.css"

type JsonObject = Record<string, unknown>
type Mode = "followers" | "account_audience" | "account_commenters" | "commenters"
type Engine = "kiara" | "mailerfind"
type Notice = { title: string; text: string }

const modes: Record<Mode, { label: string; description: string; placeholder: string; icon: typeof UsersRound }> = {
  followers: { label: "Seguidores", description: "Pessoas que seguem o perfil", placeholder: "@perfilconcorrente", icon: UsersRound },
  account_audience: { label: "Audiência engajada", description: "Curtidas e comentários recentes", placeholder: "@perfilconcorrente", icon: Radar },
  account_commenters: { label: "Comentaristas da conta", description: "Pessoas que respondem às publicações", placeholder: "@perfilconcorrente", icon: MessageCircleMore },
  commenters: { label: "Comentários de publicação", description: "Leads de um post ou Reel específico", placeholder: "https://instagram.com/p/...", icon: AtSign },
}

function asObject(value: unknown): JsonObject { return value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {} }
function firstString(value: JsonObject, keys: string[]) { for (const key of keys) if (typeof value[key] === "string") return value[key] as string; return "" }
function firstNumber(value: JsonObject, keys: string[]) { for (const key of keys) if (typeof value[key] === "number") return value[key] as number; return undefined }
function findItems(value: unknown, keys: string[]): JsonObject[] {
  if (Array.isArray(value)) return value.filter((item) => item && typeof item === "object") as JsonObject[]
  const object = asObject(value)
  for (const key of keys) if (Array.isArray(object[key])) return findItems(object[key], keys)
  for (const key of ["data", "result"]) if (object[key]) { const nested = findItems(object[key], keys); if (nested.length) return nested }
  return []
}
function findIdentifier(value: unknown): string {
  const object = asObject(value)
  const direct = firstString(object, ["id", "analysisId", "analysis_id"])
  if (direct) return direct
  for (const key of ["analysis", "data", "result"]) if (object[key]) { const nested = findIdentifier(object[key]); if (nested) return nested }
  return ""
}
function analysisRecord(value: unknown): JsonObject {
  const object = asObject(value)
  if (!Object.keys(object).length) return {}
  if (firstString(object, ["status", "state"]) || findIdentifier(object)) return object
  for (const key of ["analysis", "data", "result"]) {
    const nested = analysisRecord(object[key])
    if (Object.keys(nested).length) return nested
  }
  return object
}
function analysisStatus(value: unknown) { return firstString(analysisRecord(value), ["status", "state"]).toUpperCase() }
function isRunning(value: unknown) { return ["RUNNING", "STARTING", "QUEUED", "PROCESSING", "PENDING"].includes(analysisStatus(value)) }
function isFinished(value: unknown) { return ["COMPLETED", "FINISHED", "DONE", "PAUSED", "FAILED", "CANCELLED"].includes(analysisStatus(value)) }
function statusLabel(value: unknown) {
  const labels: Record<string, string> = {
    CANCELLED: "Cancelada",
    COMPLETED: "Concluída",
    DONE: "Concluída",
    FAILED: "Não concluída",
    FINISHED: "Concluída",
    PAUSED: "Concluída",
  }
  return isRunning(value) ? "Pesquisa em andamento" : labels[analysisStatus(value)] ?? "Criada"
}
function instagramUrl(username: string) {
  const handle = username.trim().replace(/^https?:\/\/(?:www\.)?instagram\.com\//i, "").replace(/^@/, "").split(/[/?#]/)[0]
  return handle ? `https://www.instagram.com/${encodeURIComponent(handle)}/` : ""
}
async function bodyOrError(response: Response) {
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body?.error?.message ?? "Não foi possível concluir a operação.")
  return body
}

export function CompetitionConsole() {
  const [engine, setEngine] = useState<Engine>("kiara")
  const [mode, setMode] = useState<Mode>("followers")
  const [target, setTarget] = useState("")
  const [importedProfiles, setImportedProfiles] = useState("")
  const [overview, setOverview] = useState<JsonObject>({})
  const [prepared, setPrepared] = useState<JsonObject | null>(null)
  const [prospects, setProspects] = useState<JsonObject[]>([])
  const [selectedAnalysis, setSelectedAnalysis] = useState("")
  const [trackingId, setTrackingId] = useState("")
  const [liveAnalysis, setLiveAnalysis] = useState<JsonObject | null>(null)
  const [loading, setLoading] = useState<"overview" | "create" | "start" | "prospects" | null>("overview")
  const [notice, setNotice] = useState<Notice | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading("overview")
    try {
      const response = await fetch("/api/competition/overview", { cache: "no-store" })
      setOverview(await bodyOrError(response))
    } catch (error) {
      setNotice({ title: "Concorrência indisponível", text: error instanceof Error ? error.message : "Falha ao consultar o MailerFind." })
    } finally { setLoading(null) }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function initialLoad() {
      try {
        const response = await fetch("/api/competition/overview", { cache: "no-store" })
        const body = await bodyOrError(response)
        if (!cancelled) setOverview(body)
      } catch (error) {
        if (!cancelled) setNotice({ title: "Concorrência indisponível", text: error instanceof Error ? error.message : "Falha ao consultar o MailerFind." })
      } finally {
        if (!cancelled) setLoading(null)
      }
    }
    void initialLoad()
    return () => { cancelled = true }
  }, [])

  const analyses = useMemo(() => findItems(overview.analyses, ["analyses", "items"]), [overview])
  const activeFromOverview = useMemo(() => analyses.find(isRunning) ?? null, [analyses])
  const activeId = trackingId || findIdentifier(activeFromOverview)
  const liveRecord = analysisRecord(liveAnalysis ?? activeFromOverview)
  const liveName = firstString(liveRecord, ["name", "target", "username"]) || "Audiência selecionada"
  const liveCount = firstNumber(liveRecord, ["prospectsCount", "prospectCount", "prospect_count", "totalProspects"]) ?? 0
  const liveProgress = firstNumber(liveRecord, ["progress", "progressPercent", "percentage"])
  const progressValue = typeof liveProgress === "number" ? Math.min(100, Math.max(0, liveProgress <= 1 ? liveProgress * 100 : liveProgress)) : null
  const account = asObject(overview.account)
  const provider = asObject(overview.provider)
  const providerAvailable = provider.available !== false
  const accountData = Object.keys(asObject(account.data)).length ? asObject(account.data) : account
  const plan = providerAvailable ? firstString(accountData, ["plan", "planName", "subscriptionPlan"]) || "Conta conectada" : "Arquivo disponível"
  const analysisCredits = asObject(accountData.analysisCredits ?? accountData.analysis_credits)
  const credits = firstNumber(analysisCredits, ["remaining", "balance", "creditsRemaining"])
    ?? firstNumber(accountData, ["creditsRemaining", "credits"])

  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    async function poll() {
      try {
        const response = await fetch(`/api/competition/analyses/${encodeURIComponent(activeId)}`, { cache: "no-store" })
        const body = await bodyOrError(response)
        if (cancelled) return
        setLiveAnalysis(body)
        if (isFinished(body)) {
          const [overviewResponse, prospectsResponse] = await Promise.all([
            fetch("/api/competition/overview", { cache: "no-store" }),
            fetch(`/api/competition/prospects?${new URLSearchParams({ analysis_id: activeId, limit: "100" })}`, { cache: "no-store" }),
          ])
          const [overviewBody, prospectsBody] = await Promise.all([bodyOrError(overviewResponse), bodyOrError(prospectsResponse)])
          if (cancelled) return
          setOverview(overviewBody)
          setProspects(findItems(prospectsBody, ["prospects", "items"]))
          setSelectedAnalysis(activeId)
          setTrackingId("")
          setLiveAnalysis(null)
          return
        }
      } catch {
        // A falha transitória é tentada novamente sem interromper a experiência.
      }
      if (!cancelled) timer = setTimeout(() => void poll(), 4_000)
    }
    void poll()
    return () => { cancelled = true; if (timer) clearTimeout(timer) }
  }, [activeId])

  async function createAnalysis(event: React.FormEvent) {
    event.preventDefault(); setLoading("create"); setNotice(null); setPrepared(null)
    try {
      const response = await fetch("/api/competition/analyses", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, target, name: `Kiara · ${modes[mode].label} · ${target}` }),
      })
      const body = await bodyOrError(response)
      if (!findIdentifier(body)) throw new Error("O MailerFind criou a análise, mas não retornou seu identificador. Atualize a lista antes de tentar novamente.")
      setPrepared(body)
      await loadOverview()
    } catch (error) {
      setNotice({ title: "Não foi possível preparar", text: error instanceof Error ? error.message : "Revise o perfil informado." })
    } finally { setLoading(null) }
  }

  async function startAnalysis() {
    const id = findIdentifier(prepared)
    if (!id) return
    setLoading("start"); setNotice(null)
    try {
      const response = await fetch(`/api/competition/analyses/${encodeURIComponent(id)}/start`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }),
      })
      const body = await bodyOrError(response)
      setPrepared(null)
      setSelectedAnalysis(id)
      setTrackingId(id)
      setLiveAnalysis(body)
      await loadOverview()
    } catch (error) {
      setNotice({ title: "Coleta não iniciada", text: error instanceof Error ? error.message : "Verifique os créditos e o plano MailerFind." })
    } finally { setLoading(null) }
  }

  async function importProfiles(event: React.FormEvent) {
    event.preventDefault(); setLoading("create"); setNotice(null); setPrepared(null)
    try {
      const profiles = importedProfiles.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean)
      const response = await fetch("/api/competition/imports", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, target, profiles, name: `Kiara · ${modes[mode].label} · ${target}` }),
      })
      const body = await bodyOrError(response)
      const id = findIdentifier(asObject(body.analysis))
      if (!id) throw new Error("A lista foi recebida, mas não foi possível criar o arquivo da análise.")
      setImportedProfiles("")
      await loadOverview()
      await loadProspects(id)
    } catch (error) {
      setNotice({ title: "Não foi possível importar", text: error instanceof Error ? error.message : "Revise os perfis informados." })
    } finally { setLoading(null) }
  }

  async function loadProspects(analysisId: string) {
    setSelectedAnalysis(analysisId); setLoading("prospects"); setProspects([]); setNotice(null)
    try {
      const query = new URLSearchParams({ analysis_id: analysisId, limit: "100" })
      const response = await fetch(`/api/competition/prospects?${query}`, { cache: "no-store" })
      const body = await bodyOrError(response)
      setProspects(findItems(body, ["prospects", "items"]))
    } catch (error) {
      setNotice({ title: "Prospectos indisponíveis", text: error instanceof Error ? error.message : "A análise pode ainda estar processando." })
    } finally { setLoading(null) }
  }

  return <div className={styles.page}>
    <header className={styles.header}>
      <div><p>Prévia exclusiva do administrador</p><h1>Inteligência de concorrência</h1><span>Transforme audiências públicas do Instagram em oportunidades analisáveis.</span></div>
      <Badge variant="outline" className={styles.connected}><i /> Motor próprio da Kiara</Badge>
    </header>

    {notice && <Alert variant="destructive"><ShieldCheck /><AlertTitle>{notice.title}</AlertTitle><AlertDescription>{notice.text}</AlertDescription></Alert>}

    <div className={styles.workspace}>
      <Card className={styles.builder}>
        <CardHeader><CardTitle>Nova análise</CardTitle><CardDescription>{engine === "kiara" ? "Importe perfis públicos capturados e salve tudo no arquivo da Kiara." : "Crie primeiro; a coleta só começa após sua confirmação."}</CardDescription></CardHeader>
        <CardContent>
          <div className={styles.engineTabs} role="tablist" aria-label="Motor da análise">
            <button type="button" role="tab" aria-selected={engine === "kiara"} onClick={() => setEngine("kiara")}><Sparkles />Kiara própria <small>sem créditos</small></button>
            <button type="button" role="tab" aria-selected={engine === "mailerfind"} onClick={() => setEngine("mailerfind")}><Database />MailerFind <small>opcional</small></button>
          </div>
          {engine === "kiara" ? <form onSubmit={importProfiles} className={styles.form}>
            <div className={styles.kiaraIntro}><div><ClipboardPaste /><span><strong>Cole os perfis capturados</strong><small>A extensão lê somente perfis públicos já visíveis na sua aba.</small></span></div><a href="/downloads/kiara-instagram-collector.zip" download><Download />Baixar extensão</a></div>
            <div className={styles.field}><Label htmlFor="kiara-mode">Tipo de sinal</Label><Select value={mode} onValueChange={(value) => setMode(value as Mode)}><SelectTrigger id="kiara-mode"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(modes).map(([value, item]) => <SelectItem key={value} value={value}>{item.label}</SelectItem>)}</SelectContent></Select></div>
            <div className={styles.field}><Label htmlFor="kiara-target">Perfil ou publicação analisada</Label><Input id="kiara-target" value={target} onChange={(event) => setTarget(event.target.value)} placeholder={modes[mode].placeholder} required autoComplete="off" /></div>
            <div className={styles.field}><Label htmlFor="kiara-profiles">Perfis públicos capturados</Label><Textarea id="kiara-profiles" value={importedProfiles} onChange={(event) => setImportedProfiles(event.target.value)} placeholder={"@perfil1 | Nome público\n@perfil2\nhttps://instagram.com/perfil3/"} rows={7} required /><p>Um perfil por linha. Duplicados e links inválidos são removidos automaticamente.</p></div>
            <ol className={styles.steps}><li><b>1</b>Entre no Instagram e abra seguidores ou comentários.</li><li><b>2</b>Role a lista e capture os perfis com a extensão.</li><li><b>3</b>Copie, cole acima e salve na Kiara.</li></ol>
            <Button type="submit" size="lg" disabled={loading !== null || !target.trim() || !importedProfiles.trim()}>{loading === "create" ? <Loader2 className="animate-spin" /> : <Sparkles />}Criar análise na Kiara</Button>
          </form> : <form onSubmit={createAnalysis} className={styles.form}>
            <div className={styles.field}><Label htmlFor="competition-mode">Tipo de sinal</Label><Select value={mode} onValueChange={(value) => setMode(value as Mode)}><SelectTrigger id="competition-mode"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(modes).map(([value, item]) => <SelectItem key={value} value={value}>{item.label}</SelectItem>)}</SelectContent></Select><p>{modes[mode].description}</p></div>
            <div className={styles.field}><Label htmlFor="competition-target">{mode === "commenters" ? "Link da publicação" : "Perfil do concorrente"}</Label><Input id="competition-target" value={target} onChange={(event) => setTarget(event.target.value)} placeholder={modes[mode].placeholder} required minLength={2} autoComplete="off" /><p>Use somente perfis e publicações públicas.</p></div>
            <Button type="submit" size="lg" disabled={loading !== null || !target.trim()}>{loading === "create" ? <Loader2 className="animate-spin" /> : <Search />}Preparar análise</Button>
          </form>}
          {engine === "mailerfind" && prepared && <div className={styles.confirm}><strong>Pronta para iniciar</strong><Button onClick={() => void startAnalysis()} disabled={loading !== null}>{loading === "start" ? <Loader2 className="animate-spin" /> : <Play />}Iniciar pesquisa</Button></div>}
        </CardContent>
      </Card>

      <aside className={styles.summary}>
        {engine === "kiara" ? <Card><CardHeader><CardDescription>Motor próprio da Kiara</CardDescription><CardTitle>Disponível sem créditos</CardTitle></CardHeader><CardContent className={styles.accountStats}><span><b>{analyses.length}</b> pesquisas arquivadas</span><a href="/downloads/kiara-instagram-collector.zip" download>Instalar coletor <Download /></a></CardContent></Card> : <Card><CardHeader><CardDescription>{providerAvailable ? "Conta MailerFind" : "Histórico de Concorrência"}</CardDescription><CardTitle>{plan}</CardTitle></CardHeader><CardContent className={styles.accountStats}><span><b>{providerAvailable ? credits ?? "—" : analyses.length}</b> {providerAvailable ? "créditos de análise" : "pesquisas arquivadas"}</span><a href="/app/admin?tab=integrations">{providerAvailable ? "Gerenciar conexão" : "Reconectar MailerFind"} <ExternalLink /></a></CardContent></Card>}
        <Card><CardHeader className={styles.listHeader}><div><CardTitle>Análises recentes</CardTitle><CardDescription>{analyses.length} registros encontrados</CardDescription></div><Button variant="ghost" size="icon" onClick={() => void loadOverview()} disabled={loading !== null} aria-label="Atualizar análises"><RefreshCw className={loading === "overview" ? "animate-spin" : ""} /></Button></CardHeader><CardContent className={styles.analysisList}>{analyses.length ? analyses.map((analysis, index) => { const id = firstString(analysis, ["id", "analysisId", "analysis_id"]); const name = firstString(analysis, ["name", "target", "username"]) || `Análise ${index + 1}`; const count = firstNumber(analysis, ["prospectCount", "prospectsCount", "prospect_count", "totalProspects"]); const running = isRunning(analysis); const source = firstString(analysis, ["provider"]); return <button type="button" key={id || index} onClick={() => { if (!id) return; if (running) { setSelectedAnalysis(id); setTrackingId(id) } else void loadProspects(id) }} disabled={!id || loading !== null}><span><strong>{name}</strong><small>{source === "kiara_public" ? "Kiara" : "MailerFind"} · {statusLabel(analysis)}{typeof count === "number" ? ` · ${count} leads` : ""}</small></span><Badge variant="outline">{running ? "Acompanhar" : "Ver leads"}</Badge></button> }) : <div className={styles.empty}><Radar /><p>Nenhuma análise encontrada.</p></div>}</CardContent></Card>
      </aside>
    </div>

    {activeId && <section className={styles.livePanel} role="status" aria-live="polite" aria-label="Pesquisa de concorrência em andamento">
      <div className={styles.liveVisual} aria-hidden="true"><span className={styles.liveOrbitOne} /><span className={styles.liveOrbitTwo} /><span className={styles.liveSweep} /><span className={styles.liveCore}><ScanSearch /></span><i className={styles.liveDotOne} /><i className={styles.liveDotTwo} /><i className={styles.liveDotThree} /></div>
      <div className={styles.liveContent}><span className={styles.liveEyebrow}><i /> Pesquisa em andamento</span><h2>Mapeando a audiência do concorrente</h2><p>{liveName}</p><div className={styles.liveProgress} aria-label={progressValue === null ? "Progresso em processamento" : `Progresso ${Math.round(progressValue)}%`}><span style={progressValue === null ? undefined : { width: `${progressValue}%` }} className={progressValue === null ? styles.indeterminate : ""} /></div><div className={styles.liveStages}><span className={styles.stageDone}><Database />Fonte conectada</span><span className={styles.stageActive}><ScanSearch />Coletando perfis</span><span><ListChecks />Organizando contatos</span></div></div>
      <div className={styles.liveMetric}><Sparkles /><strong>{liveCount}</strong><span>leads encontrados</span><small>Atualização automática</small></div>
    </section>}

    {!activeId && (selectedAnalysis || prospects.length > 0) && <Card><CardHeader><CardTitle>Prospectos da análise</CardTitle></CardHeader><CardContent>{loading === "prospects" ? <div className={styles.loading}><Loader2 className="animate-spin" /> Consultando prospectos…</div> : prospects.length ? <div className={styles.prospectGrid}>{prospects.map((item, index) => { const rawUsername = firstString(item, ["username", "userName", "handle"]); const username = rawUsername || `Perfil ${index + 1}`; const email = firstString(item, ["email", "publicEmail"]); const phone = firstString(item, ["phone_number", "phone", "phoneNumber"]); const instagram = firstString(item, ["profile_url", "profileUrl"]) || instagramUrl(rawUsername); const whatsapp = firstString(item, ["whatsapp_url", "whatsappUrl"]); return <article key={firstString(item, ["id", "prospectId"]) || index}><div><strong>{rawUsername ? `@${rawUsername.replace(/^@/, "")}` : username}</strong><span>{firstString(item, ["full_name", "fullName", "name"]) || "Perfil público"}</span>{email && <a className={styles.email} href={`mailto:${email}`}>{email}</a>}{phone && <span>{phone}</span>}</div><div className={styles.contactActions}>{instagram && <a className={styles.contactButton} href={instagram} target="_blank" rel="noreferrer" aria-label={`Abrir Instagram de ${username}`}><AtSign />Instagram</a>}{whatsapp && <a className={`${styles.contactButton} ${styles.whatsappButton}`} href={whatsapp} target="_blank" rel="noreferrer" aria-label={`Enviar WhatsApp para ${username}`}><MessageCircleMore />WhatsApp</a>}</div></article> })}</div> : <div className={styles.empty}><CheckCircle2 /><p>Nenhum prospecto disponível.</p></div>}</CardContent></Card>}
  </div>
}
