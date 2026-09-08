"use client"

import { useCallback, useEffect, useState } from "react"
import { BriefcaseBusiness, Check, ExternalLink, Globe2, Loader2, MapPinned, Radar, Search, ShieldCheck, Users } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type Source = "web" | "google_maps" | "instagram" | "linkedin"
type Result = { id: string; source: Source; title: string; url: string; summary: string | null }
type Job = { id: string; market: "b2c" | "b2b"; query: string; location: string | null; sources: Source[]; result_limit: number; status: string; results: Result[] }
const sourceInfo = {
  web: { label: "Web pública", detail: "Sites e páginas indexadas", icon: Globe2 },
  google_maps: { label: "Google Maps", detail: "Perfis públicos de empresas", icon: MapPinned },
  instagram: { label: "Instagram", detail: "Perfis e posts públicos indexados", icon: Users },
  linkedin: { label: "LinkedIn", detail: "Empresas e perfis públicos indexados", icon: BriefcaseBusiness },
} satisfies Record<Source, { label: string; detail: string; icon: typeof Globe2 }>

async function json(response: Response) {
  const value = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(value?.error?.message ?? "Não foi possível concluir a operação.")
  return value
}

export function HunterClient() {
  const [market, setMarket] = useState<"b2c" | "b2b">("b2c")
  const [query, setQuery] = useState("")
  const [location, setLocation] = useState("")
  const [limit, setLimit] = useState(10)
  const [sources, setSources] = useState<Source[]>(["instagram", "web"])
  const [jobs, setJobs] = useState<Job[]>([])
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const load = useCallback(async () => { try { setJobs((await json(await fetch("/api/hunter/searches", { cache: "no-store" }))).items ?? []) } catch (e) { setError(e instanceof Error ? e.message : "Falha ao carregar.") } }, [])
  // A primeira carga sincroniza a interface com o histórico persistido da API.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [load])
  const latest = jobs[0]
  function toggle(source: Source) { setSources((all) => all.includes(source) ? all.filter((item) => item !== source) : [...all, source]) }
  async function confirm() {
    setBusy(true); setError("")
    try {
      const job = await json(await fetch("/api/hunter/searches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ market, query: query.trim(), location: location.trim() || null, sources, result_limit: limit }) }))
      setReview(false)
      await json(await fetch(`/api/hunter/searches/${encodeURIComponent(job.id)}/confirm`, { method: "POST" }))
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao pesquisar."); await load() } finally { setBusy(false) }
  }
  return <div className="grid gap-6 xl:grid-cols-[1.05fr_.95fr]">
    <Card className="overflow-hidden border-border/70"><CardHeader className="border-b bg-muted/20"><div className="flex items-center justify-between"><div><CardTitle>Nova investigação</CardTitle><p className="mt-1 text-sm text-muted-foreground">Revise tudo antes de executar.</p></div><Radar className="size-6 text-primary" /></div></CardHeader><CardContent className="space-y-6 p-6">
      <fieldset><legend className="mb-2 text-sm font-medium">Mercado</legend><div className="grid grid-cols-2 gap-2">{(["b2c", "b2b"] as const).map((item) => <button key={item} type="button" onClick={() => setMarket(item)} aria-pressed={market === item} className={`rounded-xl border p-3 text-left ${market === item ? "border-primary bg-primary/10" : "hover:bg-muted/50"}`}><strong className="uppercase">{item}</strong><span className="mt-1 block text-xs text-muted-foreground">{item === "b2c" ? "Consumidores e intenção" : "Empresas e decisores"}</span></button>)}</div></fieldset>
      <div className="space-y-2"><Label htmlFor="hunter-query">O que você procura?</Label><Input id="hunter-query" className="h-11" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={market === "b2c" ? "Pessoas procurando personal trainer" : "Clínicas odontológicas em expansão"} /></div>
      <div className="grid gap-4 sm:grid-cols-[1fr_110px]"><div className="space-y-2"><Label htmlFor="hunter-location">Localização</Label><Input id="hunter-location" className="h-11" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="São Paulo, SP" /></div><div className="space-y-2"><Label htmlFor="hunter-limit">Resultados</Label><Input id="hunter-limit" className="h-11" type="number" min={1} max={20} value={limit} onChange={(e) => setLimit(Math.max(1, Math.min(20, Number(e.target.value))))} /></div></div>
      <fieldset><legend className="mb-2 text-sm font-medium">Fontes públicas</legend><div className="grid gap-2 sm:grid-cols-2">{(Object.keys(sourceInfo) as Source[]).map((source) => { const info = sourceInfo[source]; const Icon = info.icon; const active = sources.includes(source); return <button key={source} type="button" onClick={() => toggle(source)} aria-pressed={active} className={`flex items-center gap-3 rounded-xl border p-3 text-left ${active ? "border-primary/60 bg-primary/10" : "hover:bg-muted/50"}`}><Icon className="size-4"/><span className="flex-1"><strong className="block text-sm">{info.label}</strong><span className="text-xs text-muted-foreground">{info.detail}</span></span>{active && <Check className="size-4 text-primary"/>}</button> })}</div></fieldset>
      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      <Button className="h-11 w-full" disabled={query.trim().length < 2 || !sources.length || busy} onClick={() => setReview(true)}><Search/>Revisar pesquisa</Button>
    </CardContent></Card>
    <Card className="min-h-[560px] border-border/70"><CardHeader className="border-b"><div className="flex justify-between"><div><CardTitle>Resultados</CardTitle><p className="mt-1 text-sm text-muted-foreground">Evidências públicas ligadas à fonte.</p></div>{latest && <Badge variant="outline">{latest.results.length}</Badge>}</div></CardHeader><CardContent className="p-5">{!latest ? <div className="grid min-h-96 place-items-center text-center"><div><Radar className="mx-auto size-7 text-muted-foreground"/><h2 className="mt-4 font-semibold">Pronta para investigar</h2><p className="mt-2 text-sm text-muted-foreground">Configure e confirme a primeira busca.</p></div></div> : latest.status === "running" ? <div className="grid min-h-96 place-items-center"><Loader2 className="size-7 animate-spin text-primary"/></div> : <div className="space-y-3">{latest.results.map((result) => <a key={result.id} href={result.url} target="_blank" rel="noreferrer" className="block rounded-xl border p-4 hover:border-primary/50"><div className="flex gap-3"><span className="min-w-0 flex-1"><strong className="line-clamp-2 text-sm">{result.title}</strong><span className="mt-1 block text-xs text-primary">{sourceInfo[result.source].label}</span>{result.summary && <span className="mt-2 line-clamp-3 block text-xs leading-5 text-muted-foreground">{result.summary}</span>}</span><ExternalLink className="size-4 shrink-0"/></div></a>)}{!latest.results.length && <p className="py-16 text-center text-sm text-muted-foreground">Nenhum resultado público encontrado.</p>}</div>}</CardContent></Card>
    <Dialog open={review} onOpenChange={setReview}><DialogContent className="sm:max-w-lg"><DialogHeader><DialogTitle className="flex items-center gap-2"><ShieldCheck className="size-5 text-primary"/>Confirmar investigação</DialogTitle><DialogDescription>A pesquisa externa só será executada após sua confirmação.</DialogDescription></DialogHeader><div className="space-y-2 rounded-xl border bg-muted/30 p-4 text-sm"><p><strong>Mercado:</strong> {market.toUpperCase()}</p><p><strong>Busca:</strong> {query}</p><p><strong>Local:</strong> {location || "Não informado"}</p><p><strong>Fontes:</strong> {sources.map((s) => sourceInfo[s].label).join(", ")}</p><p><strong>Limite:</strong> {limit}</p></div><p className="text-xs leading-5 text-muted-foreground">Somente informações públicas. Esta confirmação não autoriza contato, mensagem ou inclusão automática no pipeline.</p><DialogFooter><Button variant="outline" onClick={() => setReview(false)}>Cancelar</Button><Button disabled={busy} onClick={() => void confirm()}>{busy ? <Loader2 className="animate-spin"/> : <ShieldCheck/>}Confirmar e pesquisar</Button></DialogFooter></DialogContent></Dialog>
  </div>
}
