"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, Ban, Search, Signal, UserCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { hunterSignals } from "@/lib/mock-data"

type HunterType = (typeof hunterSignals)[number]["type"]
const types: { value: HunterType; label: string }[] = [
  { value: "Contatável", label: "Contatáveis" },
  { value: "Sinal público", label: "Sinais públicos" },
  { value: "Bloqueado", label: "Bloqueados" },
]

export function HunterResults() {
  const [query, setQuery] = useState("")
  const [selectedTitle, setSelectedTitle] = useState(hunterSignals[0]?.title ?? "")

  return <div className="overflow-hidden rounded-2xl border bg-card">
    <div className="border-b p-4 sm:p-5">
      <div className="relative max-w-xl">
        <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} className="min-h-11 pl-9" placeholder="Buscar por pessoa, intenção ou fonte" aria-label="Buscar resultados do Hunter" />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">Resultados fictícios · scores são sinais de prioridade, não probabilidade de compra.</p>
    </div>

    <Tabs defaultValue="Contatável" onValueChange={(value) => {
      const first = hunterSignals.find((item) => item.type === value)
      if (first) setSelectedTitle(first.title)
    }}>
      <div className="overflow-x-auto border-b px-4 sm:px-5">
        <TabsList variant="line" className="h-12 gap-5">
          {types.map((type) => <TabsTrigger key={type.value} value={type.value} className="min-h-11 px-0">{type.label}<span className="font-mono text-xs text-muted-foreground">{hunterSignals.filter((item) => item.type === type.value).length}</span></TabsTrigger>)}
        </TabsList>
      </div>
      {types.map((type) => <TabsContent key={type.value} value={type.value} className="m-0"><ResultsPanel type={type.value} query={query} selectedTitle={selectedTitle} onSelect={setSelectedTitle} /></TabsContent>)}
    </Tabs>
  </div>
}

function ResultsPanel({type,query,selectedTitle,onSelect}:{type:HunterType;query:string;selectedTitle:string;onSelect:(title:string)=>void}) {
  const results = useMemo(() => hunterSignals.filter((item) => item.type === type && `${item.title} ${item.intent} ${item.source}`.toLowerCase().includes(query.toLowerCase())), [query, type])
  const selected = results.find((item) => item.title === selectedTitle) ?? results[0]

  if (!selected) return <div className="grid min-h-72 place-items-center p-8 text-center"><div><Search aria-hidden="true" className="mx-auto size-5 text-muted-foreground" /><p className="mt-3 font-medium">Nenhum resultado neste filtro</p><p className="mt-1 text-sm text-muted-foreground">Ajuste a busca para voltar a comparar os sinais.</p></div></div>

  return <div className="grid min-h-[420px] lg:grid-cols-[minmax(280px,0.72fr)_minmax(360px,1fr)]">
    <section aria-label={`Lista de ${type}`} className="border-b lg:border-b-0 lg:border-r">
      {results.map((item) => {
        const isSelected = item.title === selected.title
        return <button key={item.title} type="button" aria-pressed={isSelected} onClick={() => onSelect(item.title)} className={`relative w-full border-b p-4 text-left transition-colors last:border-b-0 hover:bg-muted/40 focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring ${isSelected?"bg-primary/[0.06]":""}`}>
          {isSelected && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-primary" />}
          <div className="flex items-start justify-between gap-3"><div><p className="font-medium">{item.title}</p><p className="mt-1 text-xs text-muted-foreground">{item.source}</p></div><span className="font-mono text-xs tabular-nums" aria-label={`Sinal demonstrativo ${item.score} de 100`}>{item.score}/100</span></div>
          <p className="mt-3 text-sm leading-5">{item.intent}</p>
          <p className="mt-2 text-xs text-muted-foreground">Atualizado há {item.freshness}</p>
        </button>
      })}
    </section>

    <section aria-label="Detalhes do resultado selecionado" className="p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4"><div><ResultType type={selected.type} /><h2 className="mt-3 text-xl font-semibold tracking-tight">{selected.title}</h2><p className="mt-1 text-sm text-muted-foreground">{selected.source} · há {selected.freshness}</p></div><div className="text-right"><p className="font-mono text-2xl font-semibold tabular-nums">{selected.score}</p><p className="text-[11px] text-muted-foreground">sinal demo / 100</p></div></div>
      <div className="mt-6 border-y py-5"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">Leitura do sinal</p><p className="mt-2 text-sm leading-6">{selected.intent}</p><p className="mt-3 text-xs leading-5 text-muted-foreground">A pontuação organiza a fila fictícia. Fonte, recência e permissão continuam sendo fatores separados.</p></div>
      <div className="mt-5 rounded-xl bg-muted/45 p-4"><p className="text-sm font-medium">Canal e próxima ação</p><p className="mt-2 text-sm leading-6 text-muted-foreground">{selected.type === "Contatável"?"A conversa foi iniciada pelo contato no Instagram. Revise o contexto na Inbox antes de preparar qualquer resposta.":selected.type === "Sinal público"?"Este é um sinal público. Ele permite revisão ou resposta pública, mas não autoriza uma DM privada.":"O opt-out prevalece. Nenhuma ação externa está disponível para este contato."}</p></div>
      <div className="mt-5">
        {selected.type === "Contatável" ? <Button asChild><Link href="/app/inbox">Abrir conversa inbound <ArrowRight aria-hidden="true" /></Link></Button> : <><Button variant="outline" disabled>{selected.type === "Sinal público"?"DM privada indisponível":"Contato bloqueado"}</Button><p className="mt-2 text-xs text-muted-foreground">{selected.type === "Sinal público"?"Adicione a uma revisão pública quando o fluxo conectado estiver disponível.":"Consulte o registro de opt-out antes de qualquer revisão."}</p></>}
      </div>
    </section>
  </div>
}

function ResultType({type}:{type:HunterType}) {
  const Icon = type === "Contatável" ? UserCheck : type === "Sinal público" ? Signal : Ban
  return <Badge variant={type === "Bloqueado"?"destructive":"outline"}><Icon aria-hidden="true" />{type}</Badge>
}
