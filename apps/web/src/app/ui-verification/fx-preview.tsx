"use client"

import { useState } from "react"
import dynamic from "next/dynamic"
import { FxPointer } from "@/components/fx/fx"
import { PipelineFunnel } from "@/components/app-shell/pipeline-funnel"
import { ConversationConstellation } from "@/components/app-shell/conversation-constellation"
import { VoiceOrb } from "@/components/chat/voice-orb"
import type { MapLead } from "@/app/(app)/app/(leads-module)/hunter/lead-map-3d"
import "@/components/fx/effects.css"

const LeadMap3D = dynamic(() => import("@/app/(app)/app/(leads-module)/hunter/lead-map-3d"), { ssr: false })

// Porto Alegre sample leads (UI verification only).
const leads: MapLead[] = [
  [-51.2177, -30.0346, "hot", 92], [-51.2090, -30.0277, "hot", 85], [-51.2290, -30.0440, "warm", 66], [-51.1960, -30.0390, "warm", 58],
  [-51.2350, -30.0200, "cold", 34], [-51.2010, -30.0520, "hot", 80], [-51.2420, -30.0360, "cold", 28], [-51.2140, -30.0600, "warm", 61],
].map(([lng, lat, temperature, score], index) => ({ id: `p${index}`, name: `Clínica exemplo ${index + 1}`, at: [lng as number, lat as number], temperature: temperature as MapLead["temperature"], score: score as number }))

export function FxPreview({ view }: { view?: string }) {
  const [stage, setStage] = useState("active")
  const [phase, setPhase] = useState<"idle" | "speaking">("speaking")
  return <div className="mx-auto max-w-5xl space-y-6 p-6">
    <FxPointer />
    <LeadMap3D scanning={view === "scan"} leads={view === "scan" ? [] : leads} total={10} query="dentista" location="Porto Alegre" />
    <PipelineFunnel counts={{ new: 14, qualified: 9, contacted: 6, opportunity: 3, won: 2, lost: 1 }} active={stage} onPick={(next) => setStage((current) => current === next ? "active" : next)} />
    <ConversationConstellation activeId="c1" onPick={() => {}} stars={Array.from({ length: 18 }, (_, index) => ({ id: `c${index}`, name: `Contato ${index + 1}`, unread: index % 4 === 0 ? 2 : 0, temperature: ["hot", "warm", "cold", "unknown"][index % 4], score: 30 + (index * 37) % 70 }))} />
    <div className="grid place-items-center rounded-2xl border bg-[#0b0a14] py-10" style={{ ["--level" as string]: phase === "speaking" ? ".6" : "0" }}>
      <VoiceOrb phase={phase} label="Orbe" onPress={() => setPhase((current) => current === "idle" ? "speaking" : "idle")} ref={(element) => { element?.style.setProperty("--level", phase === "speaking" ? ".6" : "0") }} />
    </div>
  </div>
}
