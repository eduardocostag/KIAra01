"use client"

import { useEffect, useRef } from "react"
import { AudioLines, Bot, Globe2, Sparkles, Target } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"

export function OrbitScene() {
  const sceneRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const scene = sceneRef.current
    if (!scene) return
    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)")
    let frame = 0

    function resetEyes() {
      scene?.style.setProperty("--eye-x", "0px")
      scene?.style.setProperty("--eye-y", "0px")
    }
    function followPointer(event: PointerEvent) {
      if (!scene || motionPreference.matches || event.pointerType === "touch") return
      const bounds = scene.getBoundingClientRect()
      const dx = event.clientX - (bounds.left + bounds.width / 2)
      const dy = event.clientY - (bounds.top + bounds.height / 2)
      const distance = Math.max(1, Math.hypot(dx, dy))
      const strength = Math.min(1, distance / Math.max(120, Math.min(window.innerWidth, window.innerHeight) * .34))
      const x = dx / distance * strength
      const y = dy / distance * strength
      if (frame) cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        scene.style.setProperty("--eye-x", `${(x * 19).toFixed(1)}px`)
        scene.style.setProperty("--eye-y", `${(y * 15).toFixed(1)}px`)
      })
    }

    window.addEventListener("pointermove", followPointer, { passive: true })
    motionPreference.addEventListener("change", resetEyes)
    return () => {
      window.removeEventListener("pointermove", followPointer)
      motionPreference.removeEventListener("change", resetEyes)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  return <div ref={sceneRef} className="kiara-orbit-scene">
    <span className="kiara-orbit-glow" />
    <span className="kiara-orbit-ring kiara-orbit-ring-one" />
    <span className="kiara-orbit-ring kiara-orbit-ring-two" />
    <span className="kiara-orbit-ring kiara-orbit-ring-three" />
    <span className="kiara-orbit-ring kiara-orbit-ring-four" />
    <span className="kiara-orbit-ring kiara-orbit-ring-five" />
    <span className="kiara-orbit-ring kiara-orbit-ring-six" />
    <span className="kiara-orbit-ring kiara-orbit-ring-seven" />
    <span className="kiara-orbit-arc kiara-orbit-arc-one" />
    <span className="kiara-orbit-arc kiara-orbit-arc-two" />
    <span className="kiara-orbit-arc kiara-orbit-arc-three" />
    <KiaraOrb size="lg" />
    <span className="kiara-orbit-spark kiara-orbit-spark-one" />
    <span className="kiara-orbit-spark kiara-orbit-spark-two" />
    <span className="kiara-orbit-spark kiara-orbit-spark-three" />
    <span className="kiara-orbit-moon kiara-orbit-moon-one" />
    <span className="kiara-orbit-moon kiara-orbit-moon-two" />
    <span className="kiara-orbit-moon kiara-orbit-moon-three" />
    <span className="kiara-orbit-moon kiara-orbit-moon-four" />
    <span className="kiara-orbit-moon kiara-orbit-moon-five" />
    <span className="kiara-orbit-moon kiara-orbit-moon-six" />
    <span className="kiara-orbit-callout kiara-orbit-callout-top"><Sparkles className="size-3" />Buscas organizadas</span>
    <span className="kiara-orbit-callout kiara-orbit-callout-skill"><Target className="size-3" />Leads priorizados</span>
    <span className="kiara-orbit-callout kiara-orbit-callout-right"><AudioLines className="size-3" />Próxima ação clara</span>
    <span className="kiara-orbit-callout kiara-orbit-callout-bottom"><Globe2 className="size-3" />Fontes públicas</span>
    <span className="kiara-orbit-callout kiara-orbit-callout-kiara"><Bot className="size-3" />Kiara</span>
  </div>
}
