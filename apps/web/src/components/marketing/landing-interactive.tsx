"use client"

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react"
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

  return <div ref={ref} className={styles.scene} role="img" aria-label="A Kiara no centro, conectada aos módulos Leads, WhatsApp, Chat e Automation">
    <div className={styles.stage}>
      <span className={styles.halo} />
      <span className={styles.ring} />
      <span className={cn(styles.ring, styles.ring2)} />
      <span className={cn(styles.ring, styles.ring3)} />
      <span className={styles.orb}><span className={styles.face}><i /><i /></span></span>
      <div className={cn(styles.card, styles.cardA)}><span className={styles.cardIcon}><Search /></span><span><strong>12 leads encontrados</strong><small>Dentistas · Porto Alegre</small></span></div>
      <div className={cn(styles.card, styles.cardB)}><span className={styles.cardIcon}><MessageCircle /></span><span><strong>Respondendo no WhatsApp</strong><small>Contato autorizado</small></span><i className={styles.live} /></div>
      <div className={cn(styles.card, styles.cardC)}><span className={styles.cardIcon}><Bot /></span><span><strong>“Kiara, o que priorizo?”</strong><small>Converse com a Kiara</small></span></div>
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

/** Cycles one highlighted word in place (e.g. market segments). */
export function WordRotator({ words, interval = 2200 }: { words: string[]; interval?: number }) {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    if (reducedMotion()) return
    const timer = setInterval(() => setIndex((current) => (current + 1) % words.length), interval)
    return () => clearInterval(timer)
  }, [words.length, interval])
  return <span className={styles.rotator}>
    <span className="sr-only">{words.join(", ")}</span>
    <span key={index} className={styles.rotatorWord} aria-hidden="true">{words[index]}</span>
  </span>
}

/** Final call-to-action orb: glows and leans toward the pointer. */
export function CtaOrb() {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    let frame = 0
    function move(event: PointerEvent) {
      const orb = ref.current
      if (!orb || event.pointerType === "touch" || reducedMotion()) return
      const bounds = orb.getBoundingClientRect()
      const x = Math.max(-1, Math.min(1, (event.clientX - (bounds.left + bounds.width / 2)) / 500))
      const y = Math.max(-1, Math.min(1, (event.clientY - (bounds.top + bounds.height / 2)) / 500))
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => { orb.style.setProperty("--px", x.toFixed(3)); orb.style.setProperty("--py", y.toFixed(3)) })
    }
    window.addEventListener("pointermove", move, { passive: true })
    return () => { window.removeEventListener("pointermove", move); cancelAnimationFrame(frame) }
  }, [])
  return <span ref={ref} className={styles.ctaOrb} aria-hidden="true"><span className={styles.face}><i /><i /></span></span>
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
