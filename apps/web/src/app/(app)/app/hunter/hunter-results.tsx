"use client"

import Link from "next/link"
import { useState } from "react"
import { ArrowRight, Check, CheckCheck, Copy, ExternalLink, Globe2, History, Inbox, ListFilter, Loader2, Mail, MapPin, MessageCircle, Phone, Radar, RefreshCw, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { publicPhone, publicWhatsappUrl, type HunterJob, type HunterResult } from "@/lib/api/hunter-client"
import { HunterActivity } from "./hunter-activity"
import styles from "./hunter.module.css"

const labels: Record<string, string> = { web: "Web pública", google_maps: "Google Maps", instagram: "Instagram", linkedin: "LinkedIn" }
const statuses: Record<string, string> = { completed: "Concluída", running: "Em execução", pending_confirmation: "Aguardando confirmação", failed: "Falhou", cancelled: "Cancelada" }

function readableExcerpt(summary: string | null) {
  return (summary ?? "").replace(/!\[[^\]]*\]\([^)]*\)/g, " ").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, " ").replace(/<[^>]*>/g, " ").replace(/[#*_`>|\[\]]/g, " ")
    .replace(/\s+/g, " ").trim().slice(0, 260)
}

function LeadRow({ result, location, historical }: { result: HunterResult; location: string | null; historical: boolean }) {
  const [copyStatus, setCopyStatus] = useState("")
  const data = result.public_data
  const whatsapp = publicWhatsappUrl(data?.whatsapp_url)
  const phone = publicPhone(data?.phone)
  const whatsappNumber = whatsapp ? new URL(whatsapp).hostname === "wa.me" ? new URL(whatsapp).pathname.replace(/\//g, "") : new URL(whatsapp).searchParams.get("phone") : null
  const contact = phone || (whatsappNumber ? `+${whatsappNumber}` : null)
  const synced = Boolean(data?.lead_id && data?.pipeline_entry_id)
  const excerpt = readableExcerpt(result.summary)
  const opportunity = data?.website_status === "not_listed" ? 100 : typeof data?.website_quality_score === "number" ? 100 - data.website_quality_score : null
  async function copyPhone() {
    if (!contact) return
    try { await navigator.clipboard.writeText(contact); setCopyStatus("Número copiado") }
    catch { setCopyStatus("Não foi possível copiar. Selecione o número manualmente.") }
  }
  return <article className={styles.leadCard} aria-label={result.title}>
    <div className="flex gap-3">
      <div className={styles.leadAvatar} aria-hidden="true">{result.title.trim().slice(0, 1).toUpperCase()}</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className={styles.leadTitle}>{result.title}</h3>
          {synced ? <span className="inline-flex items-center gap-1 rounded-md bg-success-subtle px-2 py-1 text-[10px] font-medium text-success"><CheckCheck className="size-3" />No pipeline</span> : <span className="rounded-md bg-muted px-2 py-1 text-[10px] text-muted-foreground">{historical ? "Histórico · não validado" : "Sem inclusão no CRM"}</span>}
        </div>
        <p className="mt-1 flex items-start gap-1.5 text-xs leading-5 text-muted-foreground"><MapPin className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" /><span className="break-words">{data?.address || location || "Localização não informada"}</span></p>
        {(opportunity !== null || data?.match_reasons?.length) && <div className={styles.intelligenceStrip}>
          {opportunity !== null && <div className="flex items-center gap-2 pr-2"><span className="grid size-9 place-items-center rounded-full bg-primary/10 font-mono text-xs font-semibold text-primary">{opportunity}</span><div><p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Potencial digital</p><p className="text-xs font-medium">{opportunity >= 70 ? "Alta oportunidade" : opportunity >= 40 ? "Pode melhorar" : "Presença estruturada"}</p></div></div>}
          {data?.match_reasons?.slice(0, 3).map(reason => <span key={reason} className="inline-flex items-center gap-1 rounded-full border bg-background px-2.5 py-1 text-[10px] text-muted-foreground"><Sparkles className="size-3 text-primary" />{reason}</span>)}
        </div>}
        <div className={styles.contactActions}>
          {contact ? <div className="inline-flex min-h-10 max-w-full items-center gap-2 rounded-lg border bg-background py-1 pl-3 pr-1"><Phone className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" /><span className="break-all font-mono text-sm font-medium tracking-tight">{contact}</span><Button variant="ghost" size="icon" className="size-8" onClick={() => void copyPhone()} aria-label={`Copiar telefone de ${result.title}`}>{copyStatus === "Número copiado" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}</Button></div> : <span className="flex min-h-10 items-center gap-2 text-xs text-muted-foreground"><Phone className="size-3.5" />Telefone não encontrado na fonte</span>}
          {whatsapp && <Button asChild className="h-10 gap-2"><a href={whatsapp} target="_blank" rel="noopener noreferrer"><MessageCircle className="size-4" />Abrir WhatsApp<ExternalLink className="size-3" /><span className="sr-only">em nova aba</span></a></Button>}
          {data?.email && <a className="inline-flex min-h-10 items-center gap-2 rounded-lg border bg-background px-3 text-xs font-medium text-foreground hover:border-primary/40" href={`mailto:${data.email}`}><Mail className="size-3.5 text-muted-foreground" />{data.email}</a>}
        </div>
        {copyStatus && <p role="status" className="mt-1 text-xs text-muted-foreground">{copyStatus}</p>}
        <p className="mt-2 text-[11px] text-muted-foreground">{whatsapp ? "Link de WhatsApp identificado na fonte pública. Nenhuma mensagem enviada." : phone ? "Número público para verificar no WhatsApp · conta ainda não confirmada." : "A Kiara não inventa contatos ausentes."}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-dashed pt-3 text-xs">
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">{data?.website_status === "not_listed" ? <ShieldCheck className="size-3.5 text-success" /> : <Globe2 className="size-3.5" />}{data?.website_status === "not_listed" ? "Site não informado no Google Maps" : data?.website_status === "present" ? "Site identificado" : "Presença digital não verificada"}</span>
          <a href={result.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-8 items-center gap-1 text-primary underline-offset-4 hover:underline">{labels[result.source]}<ExternalLink className="size-3" /><span className="sr-only">Abrir fonte em nova aba</span></a>
        </div>
        {(data?.criterion_status === "not_verified" || historical) && <p className="mt-2 text-xs leading-5 text-warning">{historical ? "Pesquisa anterior à verificação de critérios. Refaça a busca para validar e integrar os leads." : `Objetivo ainda não comprovado${data?.research_objective ? `: ${data.research_objective}` : ". Revise as evidências antes de prospectar."}`}</p>}
        {(data?.website_evidence || excerpt) && <details className="mt-2 text-xs text-muted-foreground"><summary className="w-fit cursor-pointer py-1 font-medium underline-offset-4 hover:text-foreground hover:underline">Ver evidências da fonte</summary><p className="mt-2 max-w-2xl break-words leading-5">{data?.website_evidence || excerpt}</p></details>}
      </div>
    </div>
  </article>
}

export function HunterResults({ jobs, selected, busy, loading, stage, error, onRefresh, onSelect, onBroaden }: {
  jobs: HunterJob[]; selected?: HunterJob; busy: boolean; loading: boolean; stage: string; error: string
  onRefresh: () => void; onSelect: (id: string) => void; onBroaden: (job: HunterJob) => void
}) {
  const synced = selected?.results.filter((result) => result.public_data?.lead_id && result.public_data?.pipeline_entry_id).length ?? 0
  const historical = Boolean(selected && !selected.validation)
  const withPhone = selected?.results.filter(result => publicPhone(result.public_data?.phone)).length ?? 0
  const noSite = selected?.results.filter(result => result.public_data?.website_status === "not_listed").length ?? 0
  const highOpportunity = selected?.results.filter(result => result.public_data?.website_status === "not_listed" || (typeof result.public_data?.website_quality_score === "number" && result.public_data.website_quality_score <= 55)).length ?? 0
  return <Card className={styles.resultsCard}>
    <CardHeader className={styles.resultsHeader}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className={styles.resultsEyebrow}>RADAR DE OPORTUNIDADES</p><CardTitle className={styles.resultsTitle}>Resultados da pesquisa</CardTitle></div>
        <Button variant="outline" className="h-9 text-xs" disabled={loading || busy} onClick={onRefresh}>{loading ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}Atualizar resultados</Button>
      </div>
      {jobs.length > 0 && <div className="min-w-0 space-y-2">
        <label htmlFor="hunter-history" className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground"><History className="size-3.5" />Histórico de pesquisas</label>
        <Select disabled={busy} value={selected?.id ?? jobs[0].id} onValueChange={onSelect}>
          <SelectTrigger id="hunter-history" className="h-10 w-full min-w-0 bg-background"><SelectValue /></SelectTrigger>
          <SelectContent position="popper" className="max-w-[calc(100vw-3rem)]">{jobs.map((job) => <SelectItem key={job.id} value={job.id}><span className="block max-w-[60vw] truncate sm:max-w-lg">{job.query} · {statuses[job.status]} · {job.results.length} resultados</span></SelectItem>)}</SelectContent>
        </Select>
      </div>}
    </CardHeader>
    <CardContent className="p-0">
      {error && <div role="alert" className="m-4 flex gap-3 rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-sm"><TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" /><div><strong className="block">Não foi possível concluir a consulta</strong><p className="mt-1 text-xs leading-5 text-muted-foreground">{error}</p>{selected?.results.length ? <p className="mt-2 text-xs">Os resultados já carregados continuam disponíveis abaixo.</p> : null}</div></div>}
      {busy ? <HunterActivity stage={stage} /> : loading && !selected ? <div role="status" className="grid min-h-80 place-items-center text-center text-sm text-muted-foreground"><div><Loader2 className="mx-auto mb-3 size-6 animate-spin motion-reduce:animate-none" />Carregando pesquisas salvas…</div></div> : !selected ? !error && <div className="flex min-h-96 flex-col items-center justify-center px-6 py-12 text-center"><div className="grid size-14 place-items-center rounded-xl border bg-muted/50"><Radar className="size-6 text-primary" /></div><h2 className="mt-5 text-lg font-semibold tracking-tight">Sua próxima oportunidade começa aqui</h2><p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">Defina um público e os contatos que precisa. Os resultados aparecerão aqui, com evidências e conexão ao seu pipeline.</p><div className="mt-8 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground"><span className="rounded-md bg-muted px-2 py-1">Pesquisar</span><ArrowRight className="size-3" /><span className="rounded-md bg-muted px-2 py-1">Verificar</span><ArrowRight className="size-3" /><span className="rounded-md bg-muted px-2 py-1">Organizar no CRM</span></div><p className="mt-6 text-xs text-muted-foreground">Nenhuma pesquisa registrada</p></div> : <>
        <div className={styles.summaryBlock}>
          <div role="status" aria-live="polite" className="flex items-start gap-3"><div className="grid size-9 shrink-0 place-items-center rounded-lg bg-muted">{selected.status === "completed" ? <Check className="size-4 text-success" /> : <Radar className="size-4 text-primary" />}</div><div className="min-w-0"><h2 className="font-semibold">{selected.status === "completed" ? `Pesquisa concluída: ${selected.results.length} resultado${selected.results.length === 1 ? "" : "s"}` : statuses[selected.status]}</h2><p className="mt-1 break-words text-xs text-muted-foreground">{selected.query}{selected.location ? ` · ${selected.location}` : ""}</p></div></div>
          {selected.validation && <dl className={styles.metrics}><div><dd>{selected.results.length}</dd><dt>Leads validados</dt></div><div><dd>{withPhone}</dd><dt>Com telefone</dt></div><div><dd>{noSite}</dd><dt>Sem site listado</dt></div><div><dd>{highOpportunity}</dd><dt>Oportunidade digital</dt></div></dl>}
          {synced > 0 && <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-success-subtle px-3 py-2.5 text-xs text-success"><span className="inline-flex items-center gap-2"><CheckCheck className="size-4" />{synced} lead{synced === 1 ? "" : "s"} no CRM</span><Link href="/app/pipeline" className="inline-flex min-h-8 items-center gap-1 font-semibold underline-offset-4 hover:underline">Abrir pipeline<ArrowRight className="size-3" /></Link></div>}
        </div>
        {selected.warnings && selected.warnings.length > 0 && <div className="border-b bg-warning-subtle/35 px-4 py-3 sm:px-5"><p className="mb-1 flex items-center gap-2 text-xs font-medium text-warning"><TriangleAlert className="size-3.5" />Observações da pesquisa</p><ul className="list-disc space-y-1 pl-5 text-xs leading-5 text-muted-foreground">{selected.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul></div>}
        {selected.status === "running" && <p className="p-5 text-sm leading-6 text-muted-foreground">A última atualização indica que a pesquisa está em execução. Use Atualizar resultados para consultar o estado atual.</p>}
        {selected.status === "failed" && <p role="alert" className="p-5 text-sm text-destructive">A fonte externa não concluiu a pesquisa. Tente novamente ou escolha outras fontes.</p>}
        {selected.status === "cancelled" && <p className="p-5 text-sm">Esta pesquisa foi cancelada.</p>}
        {selected.status === "pending_confirmation" && <p className="p-5 text-sm text-muted-foreground">A pesquisa foi registrada, mas a execução ainda não foi confirmada. Prepare e confirme uma nova busca.</p>}
        {selected.status === "completed" && !selected.results.length && <div className="flex min-h-64 flex-col items-center justify-center px-6 py-10 text-center"><ListFilter className="size-7 text-muted-foreground" /><h3 className="mt-4 font-semibold">Nenhum resultado encontrado</h3><p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Nenhum contato atendeu aos filtros com evidência suficiente nas fontes consultadas. Revise a região ou os critérios; dados não confirmados não são apresentados como correspondências.</p><Button variant="outline" className="mt-5 h-10" onClick={() => onBroaden(selected)}>Ajustar pesquisa</Button></div>}
        <div className={styles.leadsGrid}>{selected.results.map((result) => <LeadRow key={result.id} result={result} location={selected.location} historical={historical} />)}</div>
        {synced > 0 && <div className="flex flex-wrap items-center justify-between gap-2 border-t bg-muted/30 px-4 py-3 sm:px-5"><p className="max-w-sm text-xs leading-5 text-muted-foreground">Seus leads estão organizados. Conversas só aparecem após uma interação real.</p><Button asChild variant="ghost" className="h-9 text-xs"><Link href="/app/inbox"><Inbox className="size-3.5" />Ver contatos do Inbox<ArrowRight className="size-3.5" /></Link></Button></div>}
      </>}
    </CardContent>
  </Card>
}
