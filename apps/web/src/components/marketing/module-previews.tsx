import type { CSSProperties } from "react"
import { Megaphone, Play, Sparkles, Users } from "lucide-react"
import { cn } from "@/lib/utils"
import styles from "./landing.module.css"

/** Illustrative mini previews of each module (no real customer data). */
export function LeadsPreview() {
  const rows: [string, string, string, string][] = [
    ["CA", "Clínica Aurora", "Novo", "rgb(56 189 248 / .18)"],
    ["SS", "Studio Sorriso", "Qualificado", "rgb(167 139 250 / .25)"],
    ["OP", "Odonto Prime", "Em contato", "rgb(250 204 21 / .18)"],
    ["DB", "Dental Blanc", "Oportunidade", "rgb(232 121 249 / .2)"],
  ]
  return <div className={styles.preview} aria-hidden="true">
    {rows.map(([initials, name, stage, tone]) => <div key={name} className={styles.leadRow}><span className={styles.avatar}>{initials}</span>{name}<span className={styles.pill} style={{ background: tone }}>{stage}</span></div>)}
  </div>
}

export function WhatsAppPreview() {
  return <div className={styles.preview} aria-hidden="true"><div className={styles.bubbles}>
    <span className={cn(styles.bubble, styles.bubbleIn)}>Oi! Vocês fazem site com agendamento?</span>
    <span className={cn(styles.bubble, styles.bubbleOut)} style={{ animationDelay: ".5s" }}>Fazemos sim! O plano com agenda online inclui domínio e suporte. Quer que eu envie a proposta?</span>
    <span className={cn(styles.bubble, styles.bubbleIn)} style={{ animationDelay: "1s" }}>Quero, por favor 🙌</span>
    <span className={styles.typing}><i /><i /><i /></span>
  </div></div>
}

export function VoicePreview() {
  const bars = [10, 18, 26, 14, 22, 30, 16, 24, 12, 20]
  return <div className={styles.preview} aria-hidden="true"><div className={styles.voice}><span className={styles.voiceOrb} /></div>
    <div className={styles.wave}>{bars.map((height, index) => <i key={index} style={{ height, animationDelay: `${index * .09}s` } as CSSProperties} />)}</div>
  </div>
}

export function AutomationPreview() {
  const nodes = [
    { label: "Toda segunda", icon: Play, tone: "#f5a524", left: "6%", top: "18%" },
    { label: "Kiara escreve", icon: Sparkles, tone: "#a78bfa", left: "38%", top: "40%" },
    { label: "Instagram", icon: Users, tone: "#e879f9", left: "68%", top: "16%" },
    { label: "Meta Ads", icon: Megaphone, tone: "#facc15", left: "68%", top: "68%" },
  ]
  return <div className={styles.preview} aria-hidden="true">
    <svg className={styles.flowSvg} viewBox="0 0 400 216" preserveAspectRatio="none">
      <path className={styles.flowPath} d="M 110 52 C 150 52, 130 100, 165 100" />
      <path className={styles.flowPath} d="M 260 100 C 290 100, 250 46, 285 46" />
      <path className={styles.flowPath} d="M 260 100 C 290 100, 250 158, 285 158" />
    </svg>
    {nodes.map(({ label, icon: Icon, tone, left, top }) => <span key={label} className={styles.flowNode} style={{ left, top, "--tone": tone } as CSSProperties}><Icon />{label}</span>)}
  </div>
}
