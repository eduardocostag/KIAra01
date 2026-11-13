"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import type { HunterSource } from "@/lib/api/hunter-client"

const sourceLabels: Record<HunterSource, string> = { web: "Web", google_maps: "Google Maps", instagram: "Instagram", facebook: "Facebook" }

export function HunterActivity({ stage, query, location, sources, foundCount = 0 }: {
  stage: string
  query?: string
  location?: string | null
  sources?: HunterSource[]
  foundCount?: number
}) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  const activeSources = sources?.length ? sources : ["web", "google_maps"] as HunterSource[]

  return <div className="flex flex-col items-center px-6 py-14 text-center">
    <Loader2 className="size-6 animate-spin text-primary motion-reduce:animate-none" aria-hidden="true" />
    <p className="mt-4 font-medium" role="status" aria-live="polite">{stage}</p>
    {query ? <p className="mt-1 text-sm text-muted-foreground">{query}{location ? ` · ${location}` : ""}</p> : null}
    <ul className="mt-4 flex flex-wrap justify-center gap-2" aria-label="Fontes consultadas">{activeSources.map((source, index) => <li key={source} style={{ animationDelay: `${index * 0.35}s` }} className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs motion-safe:animate-pulse">
      <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />{sourceLabels[source]}</li>)}</ul>
    <div className="mt-4 h-1 w-full max-w-xs overflow-hidden rounded-full bg-muted" aria-hidden="true"><div className="fx-skeleton h-full w-full" style={{ background: "linear-gradient(90deg, transparent, var(--primary), transparent)", backgroundSize: "50% 100%", backgroundRepeat: "no-repeat" }} /></div>
    <p className="mt-3 text-xs text-muted-foreground">{foundCount} encontrado{foundCount === 1 ? "" : "s"} · {seconds}s</p>
    {seconds >= 60 ? <p className="mt-4 max-w-sm text-xs text-muted-foreground">Uma fonte está demorando mais que o normal. A busca fica salva e continua sozinha.</p> : null}
  </div>
}
