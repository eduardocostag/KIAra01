"use client"

import { useEffect, useState } from "react"
import { AtSign, Globe2, MapPin, MessagesSquare, Radar } from "lucide-react"
import type { HunterSource } from "@/lib/api/hunter-client"
import styles from "./hunter.module.css"

const sourceDetails = {
  web: { label: "Web", icon: Globe2 },
  google_maps: { label: "Maps", icon: MapPin },
  instagram: { label: "Instagram", icon: AtSign },
  facebook: { label: "Facebook", icon: MessagesSquare },
} satisfies Record<HunterSource, { label: string; icon: typeof Globe2 }>

const scanPoints = [
  [18, 30], [29, 63], [39, 42], [48, 72], [57, 27], [67, 55], [77, 35], [84, 68],
] as const

const pinPositions = [[20, 30], [72, 25], [31, 67], [64, 61], [82, 73]] as const

function shortLocation(value: string) {
  const parts = value.split(",").map((part) => part.trim()).filter(Boolean)
  return parts.slice(0, 2).join(", ") || value
}

export function HunterActivity({ stage, query, location, sources, foundCount = 0, discoveries = [] }: {
  stage: string
  query?: string
  location?: string | null
  sources?: HunterSource[]
  foundCount?: number
  discoveries?: string[]
}) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])

  const activeSources: HunterSource[] = sources?.length ? sources : ["web", "google_maps"]
  const place = location?.trim() || "Região selecionada"
  const progressLabel = /registrando/i.test(stage) ? "Preparando a busca" : /fila|aguardando|retomando/i.test(stage) ? "Organizando a investigação" : "Mapeando oportunidades"
  const confirmedPlaces = [...new Set(discoveries.map((item) => item.trim()).filter(Boolean))].slice(0, pinPositions.length)

  return <div className={styles.liveSearch}>
    <p className="sr-only" role="status" aria-live="polite">{stage}. {foundCount} resultado{foundCount === 1 ? "" : "s"} confirmado{foundCount === 1 ? "" : "s"}.</p>
    <div className={styles.liveMap} aria-hidden="true">
      <div className={styles.mapJourney}><span>Brasil</span><i /> <strong>{place}</strong></div>
      <div className={styles.cityPlane}>
        <div className={styles.mapGrid} />
        <svg className={styles.mapRoutes} viewBox="0 0 600 330" preserveAspectRatio="none">
          <path d="M-30 245 C95 180 115 75 260 112 S430 290 650 145" />
          <path d="M35 40 C150 125 245 50 330 165 S475 245 610 205" />
          <path d="M165 -20 C205 88 170 205 275 355" />
          <path d="M455 -20 C390 95 505 185 420 355" />
          <path d="M-20 105 C130 195 240 260 630 35" />
        </svg>
        <div className={styles.cityBlocks}>{Array.from({ length: 14 }, (_, index) => <span key={index} />)}</div>
      </div>
      <div className={styles.mapFocus}><span /><span /><span /></div>
      <div className={styles.mapOrb}><i /><i /></div>
      <div className={styles.scanBeam} />
      {scanPoints.map(([left, top], index) => <span key={`${left}-${top}`} className={styles.scanPoint} style={{ left: `${left}%`, top: `${top}%`, animationDelay: `${index * .38}s` }} />)}
      {confirmedPlaces.map((address, index) => { const [left, top] = pinPositions[index]; return <span key={address} className={styles.discoveryPin} style={{ left: `${left}%`, top: `${top}%`, animationDelay: `${index * .16}s` }} title={address}><i><MapPin /></i><b>{shortLocation(address)}</b></span> })}
      <div className={styles.locationBadge}><MapPin />{confirmedPlaces.length ? `${confirmedPlaces.length} localidades confirmadas` : place}</div>
      <div className={styles.mapScale}>KIARA · BUSCA TERRITORIAL</div>
    </div>

    <div className={styles.liveSearchCopy}>
      <p className={styles.liveEyebrow}><Radar />{progressLabel}</p>
      <h2>{stage}</h2>
      <p className={styles.liveTarget}>{query ? <>Procurando <strong>{query}</strong> em <strong>{place}</strong></> : <>Explorando fontes públicas em <strong>{place}</strong></>}</p>
      <div className={styles.sourceProgress} aria-label="Fontes selecionadas">
        {activeSources.map((source, index) => { const detail = sourceDetails[source]; const Icon = detail.icon; return <span key={source} style={{ animationDelay: `${index * .45}s` }}><Icon />{detail.label}<i /></span> })}
      </div>
      <div className={styles.liveMeta} aria-live="off">
        <span><strong>{foundCount}</strong> confirmado{foundCount === 1 ? "" : "s"}</span>
        <span>{seconds}s decorridos</span>
      </div>
      <p className={styles.liveHint}>{foundCount ? "Novos resultados aparecem quando cada fonte confirma os dados." : "Os pontos representam áreas em varredura. Leads só aparecem depois da confirmação dos dados."}</p>
      {seconds >= 60 && <p className={styles.slowSource}>Uma fonte está demorando mais que o habitual. A pesquisa permanece salva e continuará com segurança.</p>}
    </div>
  </div>
}
