"use client"

import { Lock } from "lucide-react"
import { splitCountdown, useLaunchCountdown } from "./coming-soon"

/** Compact live countdown for module cards that are still in early access. */
export function LaunchBadge() {
  const left = useLaunchCountdown()
  const parts = left === null ? null : splitCountdown(left)
  const units = [["dias", parts?.days], ["h", parts?.hours], ["min", parts?.minutes], ["seg", parts?.seconds]] as const
  if (left === 0) return <span className="mb-4 inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">Liberando em instantes</span>
  return <div className="mb-5 flex flex-col items-center gap-2" role="timer" aria-label="Contagem regressiva para o lançamento">
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[10px] font-semibold uppercase tracking-[.26em] text-primary">
      <Lock className="size-3" aria-hidden="true" />Lançamento em
    </span>
    <div className="flex gap-1.5">
      {units.map(([label, value]) => <span key={label} className="flex w-11 flex-col items-center rounded-lg border border-white/10 bg-white/[.04] py-1.5">
        <span className="text-base font-semibold leading-none tabular-nums text-white">{value === undefined ? "--" : String(value).padStart(2, "0")}</span>
        <span className="mt-1 text-[9px] uppercase leading-none tracking-wider text-white/45">{label}</span>
      </span>)}
    </div>
  </div>
}
