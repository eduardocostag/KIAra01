"use client"

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react"
import { Bot, MessageCircle, Search, Workflow } from "lucide-react"
import { cn } from "@/lib/utils"
import styles from "./landing.module.css"

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches

/** Hero: Kiara's orb with rings and floating module cards; the scene and the eyes follow the pointer. */
export function HeroScene() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let frame = 0
    function move(event: PointerEvent) {
      const scene = ref.current
      if (!scene || event.pointerType === "touch" || reducedMotion()) return
      const bounds = scene.getBoundingClientRect()
      const x = Math.max(-1, Math.min(1, (event.clientX - (bounds.left + bounds.width / 2)) / (window.innerWidth / 2)))
      const y = Math.max(-1, Math.min(1, (event.clientY - (bounds.top + bounds.height / 2)) / (window.innerHeight / 2)))
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => { scene.style.setProperty("--px", x.toFixed(3)); scene.style.setProperty("--py", y.toFixed(3)) })
    }
    window.addEventListener("pointermove", move, { passive: true })
    return () => { window.removeEventListener("pointermove", move); cancelAnimationFrame(frame) }
  }, [])

  return <div ref={ref} className={styles.scene} role="img" aria-label="A Kiara no centro, conectada aos módulos Leads, WhatsApp, Chat por voz e Automation">
    <div className={styles.stage}>
      <span className={styles.halo} />
      <span className={styles.ring} />
      <span className={cn(styles.ring, styles.ring2)} />
      <span className={cn(styles.ring, styles.ring3)} />
      <span className={styles.orb}><span className={styles.face}><i /><i /></span></span>
      <div className={cn(styles.card, styles.cardA)}><span className={styles.cardIcon}><Search /></span><span><strong>12 leads encontrados</strong><small>Dentistas · Porto Alegre</small></span></div>
      <div className={cn(styles.card, styles.cardB)}><span className={styles.cardIcon}><MessageCircle /></span><span><strong>Respondendo no WhatsApp</strong><small>Contato autorizado</small></span><i className={styles.live} /></div>
      <div className={cn(styles.card, styles.cardC)}><span className={styles.cardIcon}><Bot /></span><span><strong>“Kiara, o que priorizo?”</strong><small>Conversa por voz</small></span></div>
      <div className={cn(styles.card, styles.cardD)}><span className={styles.cardIcon}><Workflow /></span><span><strong>Post de segunda agendado</strong><small>Kiara Automation</small></span></div>
    </div>
  </div>
}

/** Card that tilts toward the pointer, with a soft light following it. */
export function TiltCard({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  function move(event: React.PointerEvent) {
    const element = ref.current
    if (!element || event.pointerType === "touch" || reducedMotion()) return
    const bounds = element.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width, y = (event.clientY - bounds.top) / bounds.height
    element.style.setProperty("--ry", `${((x - .5) * 10).toFixed(2)}deg`)
    element.style.setProperty("--rx", `${((.5 - y) * 8).toFixed(2)}deg`)
    element.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`)
    element.style.setProperty("--my", `${(y * 100).toFixed(1)}%`)
  }
  function leave() { ref.current?.style.setProperty("--rx", "0deg"); ref.current?.style.setProperty("--ry", "0deg") }
  return <div className={cn(styles.tilt, className)} onPointerMove={move} onPointerLeave={leave}><div ref={ref} className={styles.tiltInner}>{children}</div></div>
}

/** Fades content in once it scrolls into view. */
export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (reducedMotion() || !("IntersectionObserver" in window)) { element.classList.add(styles.revealed); return }
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { element.classList.add(styles.revealed); observer.disconnect() } }, { threshold: .15 })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return <div ref={ref} className={cn(styles.reveal, className)} style={{ transitionDelay: `${delay}ms` } as CSSProperties}>{children}</div>
}
