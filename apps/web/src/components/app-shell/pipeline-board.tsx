"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, LayoutGrid, List, RotateCcw, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { demoLeads, type LeadStage } from "@/lib/mock-data"

const stages: LeadStage[] = ["Novo", "Em qualificação", "Qualificado", "Em conversa", "Proposta"]

const stageIds: Record<LeadStage, string> = {
  "Novo": "novo",
  "Em qualificação": "em-qualificacao",
  "Qualificado": "qualificado",
  "Em conversa": "em-conversa",
  "Proposta": "proposta",
}

export function PipelineBoard() {
  const [view, setView] = useState<"board" | "list">("list")
  const [query, setQuery] = useState("")
  const [leads, setLeads] = useState(() => demoLeads.map((lead) => ({...lead})))
  const [lastChange, setLastChange] = useState<{id:string;from:LeadStage;to:LeadStage}|null>(null)
  const filtered = useMemo(() => leads.filter((lead) => `${lead.name} ${lead.intent} ${lead.owner}`.toLowerCase().includes(query.toLowerCase())), [leads, query])

  function moveLead(id:string, to:LeadStage) {
    const lead = leads.find((item) => item.id === id)
    if (!lead || lead.stage === to) return
    setLastChange({id, from:lead.stage, to})
    setLeads((current) => current.map((item) => item.id === id ? {...item, stage:to} : item))
  }

  function undo() {
    if (!lastChange) return
    setLeads((current) => current.map((item) => item.id === lastChange.id ? {...item, stage:lastChange.from} : item))
    setLastChange(null)
  }

  return <div>
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 sm:flex-row sm:items-center">
      <div className="relative flex-1"><Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="min-h-10 pl-9" placeholder="Buscar lead, intenção ou responsável" aria-label="Buscar no pipeline" /></div>
      <div className="flex rounded-lg border p-1" role="group" aria-label="Visualização do pipeline"><Button size="sm" variant={view === "board"?"secondary":"ghost"} aria-pressed={view === "board"} onClick={() => setView("board")}><LayoutGrid aria-hidden="true" />Quadro</Button><Button size="sm" variant={view === "list"?"secondary":"ghost"} aria-pressed={view === "list"} onClick={() => setView("list")}><List aria-hidden="true" />Lista</Button></div>
    </div>

    <div className="mt-3 flex min-h-8 flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground"><p>{filtered.length} oportunidades fictícias · alterações ficam somente nesta sessão</p><div aria-live="polite">{lastChange && <div className="flex items-center gap-2"><span>Etapa alterada para {lastChange.to}.</span><Button variant="ghost" size="sm" onClick={undo}><RotateCcw aria-hidden="true" />Desfazer</Button></div>}</div></div>

    {view === "board" ? <div className="mt-4 flex snap-x gap-4 overflow-x-auto pb-4" aria-label="Quadro do pipeline">{stages.map((stage) => { const stageLeads=filtered.filter((lead)=>lead.stage===stage); const headingId=`stage-${stageIds[stage]}`; return <section key={stage} className="w-[292px] shrink-0 snap-start rounded-2xl border bg-muted/20" aria-labelledby={headingId}><header className="sticky top-0 z-10 flex items-center justify-between rounded-t-2xl border-b bg-card/95 px-4 py-3"><div><h2 id={headingId} className="text-sm font-semibold">{stage}</h2><p className="mt-0.5 text-[11px] text-muted-foreground">{stageLeads.length} nesta etapa</p></div><Badge variant="secondary" className="font-mono">{stageLeads.length}</Badge></header><div className="space-y-3 p-3">{stageLeads.length ? stageLeads.map((lead)=><LeadCard key={lead.id} lead={lead} onMove={moveLead} />) : <p className="rounded-xl border border-dashed p-5 text-center text-xs text-muted-foreground">Nenhuma oportunidade</p>}</div></section>})}</div> : <div className="mt-4 overflow-hidden rounded-xl border bg-card"><Table className="min-w-[940px]"><caption className="sr-only">Oportunidades demonstrativas por próxima ação, prazo, etapa, score e responsável</caption><TableHeader className="bg-muted/45"><TableRow><TableHead className="sticky left-0 z-10 bg-muted">Oportunidade</TableHead><TableHead>Próxima ação</TableHead><TableHead>Prazo</TableHead><TableHead>Etapa</TableHead><TableHead>Sinal demo</TableHead><TableHead>Responsável</TableHead><TableHead className="text-right">Abrir</TableHead></TableRow></TableHeader><TableBody>{filtered.map((lead)=><TableRow key={lead.id}><TableCell className="sticky left-0 bg-card"><Link className="font-medium hover:underline" href={`/app/leads/${lead.id}`}>{lead.name}</Link><p className="mt-1 text-xs text-muted-foreground">{lead.intent}</p></TableCell><TableCell className="font-medium">{lead.next}</TableCell><TableCell className="font-mono text-xs tabular-nums">{lead.due}</TableCell><TableCell><StageSelect leadId={lead.id} stage={lead.stage} onMove={moveLead} /></TableCell><TableCell><span className="font-mono tabular-nums">{lead.score}/100</span><span className="ml-2 text-xs text-muted-foreground">{lead.confidence}</span></TableCell><TableCell>{lead.owner}</TableCell><TableCell className="text-right"><Button asChild variant="ghost" size="sm"><Link href={`/app/leads/${lead.id}`} aria-label={`Abrir dossiê de ${lead.name}`}>Abrir <ArrowRight aria-hidden="true" /></Link></Button></TableCell></TableRow>)}</TableBody></Table></div>}
  </div>
}

function StageSelect({leadId,stage,onMove}:{leadId:string;stage:LeadStage;onMove:(id:string,to:LeadStage)=>void}) { return <Select value={stage} onValueChange={(value)=>onMove(leadId,value as LeadStage)}><SelectTrigger aria-label={`Alterar etapa atual ${stage}`} className="h-9 min-w-40"><SelectValue /></SelectTrigger><SelectContent>{stages.map((item)=><SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent></Select> }

function LeadCard({lead,onMove}:{lead:(typeof demoLeads)[number];onMove:(id:string,to:LeadStage)=>void}) { return <Card><CardContent className="p-4"><div className="flex items-start justify-between gap-3"><div><Link href={`/app/leads/${lead.id}`} className="font-semibold hover:underline">{lead.name}</Link><p className="mt-1 text-xs text-muted-foreground">{lead.handle}</p></div><span className="font-mono text-xs tabular-nums" aria-label={`Sinal demonstrativo ${lead.score} de 100`}>{lead.score}/100</span></div><div className="mt-4 border-l-2 border-primary pl-3"><p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Próxima ação</p><p className="mt-1 text-sm font-medium">{lead.next}</p><p className="mt-1 font-mono text-xs text-muted-foreground">{lead.due} · {lead.owner}</p></div><div className="mt-4 border-t pt-3"><StageSelect leadId={lead.id} stage={lead.stage} onMove={onMove} /></div></CardContent></Card> }
