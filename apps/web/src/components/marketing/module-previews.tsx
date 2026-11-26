import type { CSSProperties } from "react"
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

/** A business card being read: the scan line passes and the fields it found pop in. */
export function PresencialPreview() {
  const fields: [string, string][] = [["Nome", "Ana Souza"], ["WhatsApp", "(51) 99876-5432"], ["Empresa", "Pulso Marketing"], ["Sócia", "Receita Federal ✓"]]
  return <div className={styles.preview} aria-hidden="true">
    <div className={styles.scanCard}><b>Pulso</b><span>Ana Souza</span><small>Diretora Comercial</small><i className={styles.scanLine} /></div>
    <div className={styles.scanFields}>{fields.map(([label, value], index) => <span key={label} className={styles.scanField} style={{ animationDelay: `${.6 + index * .35}s` }}><small>{label}</small>{value}</span>)}</div>
  </div>
}

/** The CRM funnel: deals move from one stage to the next. */
export function PipelinePreview() {
  const columns: [string, string, string[]][] = [
    ["Novos", "#38bdf8", ["Clínica Aurora", "Pulso"]],
    ["Em contato", "#facc15", ["Odonto Prime"]],
    ["Oportunidade", "#e879f9", ["Dental Blanc"]],
  ]
  return <div className={styles.preview} aria-hidden="true"><div className={styles.board}>
    {columns.map(([title, tone, deals], column) => <div key={title} className={styles.column} style={{ "--tone": tone } as CSSProperties}>
      <small>{title}</small>
      {deals.map((deal, index) => <span key={deal} className={cn(styles.deal, column === 0 && index === 1 && styles.dealMoving)} style={{ animationDelay: `${column * .2 + index * .15}s` }}>{deal}</span>)}
    </div>)}
  </div></div>
}
