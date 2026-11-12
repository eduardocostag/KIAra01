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
    <p className="mt-3 text-xs text-muted-foreground">{activeSources.map((source) => sourceLabels[source]).join(" · ")} · {foundCount} encontrado{foundCount === 1 ? "" : "s"} · {seconds}s</p>
    {seconds >= 60 ? <p className="mt-4 max-w-sm text-xs text-muted-foreground">Uma fonte está demorando mais que o normal. A busca fica salva e continua sozinha.</p> : null}
  </div>
}
