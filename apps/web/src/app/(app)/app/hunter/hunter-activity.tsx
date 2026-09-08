"use client"

import { useEffect, useState } from "react"
import { Radar } from "lucide-react"
import styles from "./hunter.module.css"

export function HunterActivity({ stage }: { stage: string }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  return <div className={styles.activity} role="status" aria-live="polite">
    <div className={styles.radar}><Radar className="size-14" aria-hidden="true" /></div>
    <p className="text-xs uppercase tracking-[.25em] text-primary">Investigação em andamento</p>
    <h2 className="mt-3 text-xl font-semibold">{stage}</h2>
    <p className="mt-3 max-w-sm text-sm leading-6 text-muted-foreground">Aguarde nesta tela. Os resultados aparecerão assim que as fontes responderem.</p>
    <div className={styles.track} aria-hidden="true"><span /></div>
    <p className="text-xs tabular-nums text-muted-foreground" aria-live="off">{seconds}s decorridos · tempo variável por fonte</p>
    {seconds >= 60 && <p className="mt-4 text-sm text-muted-foreground">A fonte está demorando mais que o habitual. Você pode consultar o histórico ao atualizar a página.</p>}
  </div>
}
