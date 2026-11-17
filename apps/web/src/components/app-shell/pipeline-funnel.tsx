"use client"

import type { CSSProperties } from "react"
import { CountUp } from "@/components/fx/fx"
import { pipelineStages, type PipelineStage } from "@/lib/api/pipeline"

const colors: Record<PipelineStage, string> = { new: "#38bdf8", qualified: "#a78bfa", contacted: "#fbbf24", opportunity: "#e879f9", won: "#34d399", lost: "#fb7185" }
const WIDTH = 320, BAND = 40, TOP = 18, MIN = 46

/**
 * Glass funnel in perspective: each ring is a stage, its width is how many contacts are there.
 * Light particles fall through it; clicking a ring filters the list by that stage.
 */
export function PipelineFunnel({ counts, active, onPick }: { counts: Record<PipelineStage, number>; active: string; onPick: (stage: PipelineStage) => void }) {
  const stages = pipelineStages.filter((stage) => stage.id !== "lost")
  const max = Math.max(1, ...stages.map((stage) => counts[stage.id]))
  // Never wider than the ring above, so it always reads as a funnel.
  const widths = stages.map((stage) => MIN + (WIDTH - 20 - MIN) * Math.sqrt(counts[stage.id] / max))
  const rings = stages.map((stage, index) => ({
    ...stage, width: Math.min(...widths.slice(0, index + 1)) * (1 - index * .07), y: TOP + index * BAND, color: colors[stage.id],
  }))
  const height = TOP + rings.length * BAND + 10
  const center = WIDTH / 2

  return <figure className="fx-rise overflow-hidden rounded-xl border bg-card p-4" aria-label="Funil do pipeline">
    <div className="flex flex-row items-center gap-3 sm:gap-4">
      <svg viewBox={`0 0 ${WIDTH} ${height}`} className="w-[44%] max-w-[300px] shrink-0 [transform:perspective(700px)_rotateX(14deg)] sm:w-full sm:shrink" role="group" aria-label="Etapas do funil">
        <defs>
          {rings.map((ring) => <linearGradient key={ring.id} id={`funnel-${ring.id}`} x1="0" x2="1">
            <stop offset="0" stopColor={ring.color} stopOpacity=".08" />
            <stop offset=".5" stopColor={ring.color} stopOpacity=".34" />
            <stop offset="1" stopColor={ring.color} stopOpacity=".08" />
          </linearGradient>)}
          <filter id="funnel-glow"><feGaussianBlur stdDeviation="2.4" /></filter>
        </defs>
        {rings.map((ring, index) => {
          const next = rings[index + 1]
          const bottom = next ? next.width : ring.width * .82
          const y2 = ring.y + BAND
          const selected = active === ring.id
          return <g key={ring.id} role="button" tabIndex={0} aria-label={`${ring.label}: ${counts[ring.id]}`} aria-pressed={selected}
            onClick={() => onPick(ring.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(ring.id) } }}
            className="cursor-pointer outline-none [&:focus-visible>ellipse]:stroke-[3]" style={{ opacity: active === "active" || selected ? 1 : .45, transition: "opacity .3s" }}>
            <path d={`M ${center - ring.width / 2} ${ring.y} L ${center - bottom / 2} ${y2} A ${bottom / 2} 7 0 0 0 ${center + bottom / 2} ${y2} L ${center + ring.width / 2} ${ring.y} Z`} fill={`url(#funnel-${ring.id})`} />
            <ellipse cx={center} cy={ring.y} rx={ring.width / 2} ry={8} fill="none" stroke={ring.color} strokeWidth={selected ? 2.4 : 1.4} />
            {selected ? <ellipse cx={center} cy={ring.y} rx={ring.width / 2} ry={8} fill="none" stroke={ring.color} strokeWidth={4} filter="url(#funnel-glow)" /> : null}
          </g>
        })}
        {/* Leads falling through the funnel. */}
        {[0, 1, 2, 3, 4, 5].map((index) => <circle key={index} r={2.4} fill={rings[index % rings.length]?.color ?? "#a78bfa"} className="kiara-funnel-drop" style={{ "--x": `${center + Math.sin(index * 2.1) * 18}px`, "--h": `${height - 26}px`, animationDelay: `${index * .55}s` } as CSSProperties} />)}
      </svg>
      <ul className="grid min-w-0 flex-1 grid-cols-1 gap-y-1 text-[13px] sm:min-w-44 sm:gap-y-1.5 sm:text-sm">
        {rings.map((ring) => <li key={ring.id}><button type="button" onClick={() => onPick(ring.id)} aria-pressed={active === ring.id} className="flex min-h-7 w-full items-center gap-2 rounded-md px-1 text-left hover:text-foreground">
          <span className="size-2 shrink-0 rounded-full" style={{ background: ring.color, boxShadow: `0 0 10px ${ring.color}` }} aria-hidden="true" />
          <span className="text-muted-foreground">{ring.label}</span>
          <CountUp value={counts[ring.id]} className="ml-auto font-semibold tabular-nums" />
        </button></li>)}
        <li><button type="button" onClick={() => onPick("lost")} aria-pressed={active === "lost"} className="flex min-h-7 w-full items-center gap-2 rounded-md px-1 text-left text-muted-foreground hover:text-foreground">
          <span className="size-2 shrink-0 rounded-full" style={{ background: colors.lost }} aria-hidden="true" />Perdidos<CountUp value={counts.lost} className="ml-auto tabular-nums" />
        </button></li>
      </ul>
    </div>
  </figure>
}
