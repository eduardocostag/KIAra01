"use client"

import { useEffect, useRef } from "react"
import { AudioLines, Globe2, Sparkles } from "lucide-react"
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
      const x = Math.max(-1, Math.min(1, (event.clientX - bounds.left - bounds.width / 2) / Math.max(bounds.width / 2, 1)))
      const y = Math.max(-1, Math.min(1, (event.clientY - bounds.top - bounds.height / 2) / Math.max(bounds.height / 2, 1)))
      if (frame) cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        scene.style.setProperty("--eye-x", `${(x * 5).toFixed(1)}px`)
        scene.style.setProperty("--eye-y", `${(y * 4).toFixed(1)}px`)
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
    <span className="kiara-orbit-arc kiara-orbit-arc-one" />
    <span className="kiara-orbit-arc kiara-orbit-arc-two" />
    <KiaraOrb size="lg" />
    <span className="kiara-orbit-spark kiara-orbit-spark-one" />
    <span className="kiara-orbit-spark kiara-orbit-spark-two" />
    <span className="kiara-orbit-spark kiara-orbit-spark-three" />
    <span className="kiara-orbit-callout kiara-orbit-callout-top"><Sparkles className="size-3" />Buscas organizadas</span>
    <span className="kiara-orbit-callout kiara-orbit-callout-right"><AudioLines className="size-3" />Próxima ação clara</span>
    <span className="kiara-orbit-callout kiara-orbit-callout-bottom"><Globe2 className="size-3" />Fontes públicas</span>
  </div>
}
