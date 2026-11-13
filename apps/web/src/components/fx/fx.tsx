"use client"

import { useEffect, useRef, useState } from "react"

export function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

/**
 * One document-level listener drives every `.fx-spot` (spotlight) and `.fx-tilt` (3D tilt) element,
 * so cards get the effect just by adding the class; nothing re-renders.
 */
export function FxPointer() {
  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches) return
    let current: HTMLElement | null = null
    let frame = 0
    function reset(element: HTMLElement) {
      element.style.removeProperty("--rx"); element.style.removeProperty("--ry")
      element.removeAttribute("data-fx-active")
    }
    function move(event: PointerEvent) {
      const target = (event.target as Element | null)?.closest<HTMLElement>(".fx-spot, .fx-tilt") ?? null
      if (current && current !== target) reset(current)
      current = target
      if (!target) return
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const box = target.getBoundingClientRect()
        const x = event.clientX - box.left, y = event.clientY - box.top
        target.style.setProperty("--mx", `${x.toFixed(0)}px`)
        target.style.setProperty("--my", `${y.toFixed(0)}px`)
        if (target.classList.contains("fx-tilt") && !prefersReducedMotion()) {
          const strength = Number(target.dataset.tilt || 8)
          target.style.setProperty("--ry", `${((x / box.width - .5) * strength).toFixed(2)}deg`)
          target.style.setProperty("--rx", `${((.5 - y / box.height) * strength).toFixed(2)}deg`)
          target.setAttribute("data-fx-active", "")
        }
      })
    }
    function leave() { if (current) reset(current); current = null }
    document.addEventListener("pointermove", move, { passive: true })
    document.addEventListener("pointerleave", leave)
    return () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerleave", leave); cancelAnimationFrame(frame) }
  }, [])
  return null
}

/** Small particle explosion from the center of `element` (success feedback). */
export function burst(element: HTMLElement | null, color = "var(--primary)", count = 14) {
  if (!element || prefersReducedMotion()) return
  element.classList.add("fx-burst")
  for (let index = 0; index < count; index += 1) {
    const particle = document.createElement("span")
    const angle = (index / count) * Math.PI * 2 + Math.random() * .4
    const distance = 28 + Math.random() * 34
    particle.className = "fx-particle"
    particle.style.setProperty("--dx", `${Math.cos(angle) * distance}px`)
    particle.style.setProperty("--dy", `${Math.sin(angle) * distance}px`)
    particle.style.setProperty("--fx-color", color)
    particle.setAttribute("aria-hidden", "true")
    element.appendChild(particle)
    setTimeout(() => particle.remove(), 800)
  }
}

/** Number that counts up to `value` when it appears or changes. */
export function CountUp({ value, duration = 900, className }: { value: number; duration?: number; className?: string }) {
  const [shown, setShown] = useState(value)
  const from = useRef(0)
  useEffect(() => {
    const start = performance.now(), origin = from.current
    const total = prefersReducedMotion() ? 0 : duration
    let frame = 0
    const step = (now: number) => {
      const progress = total ? Math.min(1, (now - start) / total) : 1
      const eased = 1 - Math.pow(1 - progress, 3)
      setShown(Math.round(origin + (value - origin) * eased))
      if (progress < 1) frame = requestAnimationFrame(step)
      else from.current = value
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])
  return <span className={className}>{shown}</span>
}
