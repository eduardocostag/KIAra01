"use client"

import { Lock } from "lucide-react"
import { splitCountdown, useLaunchCountdown } from "./coming-soon"

/** Small live countdown for module cards that are still in early access. */
export function LaunchBadge() {
  const left = useLaunchCountdown()
  const parts = left === null ? null : splitCountdown(left)
  const pad = (value: number) => String(value).padStart(2, "0")
  return <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
    <Lock className="size-3" aria-hidden="true" />
    {left === 0 ? "Liberando em instantes" : <>Lançamento em <span className="tabular-nums">{parts ? `${parts.days}d ${pad(parts.hours)}:${pad(parts.minutes)}:${pad(parts.seconds)}` : "--"}</span></>}
  </span>
}
