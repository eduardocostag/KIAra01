import type { Ref } from "react"
import styles from "./voice-orb.module.css"
import { VoiceAura } from "./voice-aura"

export type VoicePhase = "idle" | "listening" | "thinking" | "speaking" | "error"

/**
 * Kiara's voice orb. The live audio level is written by the caller to the
 * `--level` CSS variable on this element (0..1) every animation frame, so the
 * orb reacts without re-rendering React.
 */
export function VoiceOrb({ phase, label, onPress, ref }: { phase: VoicePhase; label: string; onPress?: () => void; ref?: Ref<HTMLDivElement> }) {
  return <div ref={ref} className={styles.stage} data-state={phase}>
    <VoiceAura />
    <span className={styles.ring} aria-hidden="true" />
    <span className={styles.ring} aria-hidden="true" />
    <button type="button" className={styles.orb} onClick={onPress} aria-label={label}>
      <span className={styles.face} aria-hidden="true"><i /><i /></span>
    </button>
  </div>
}
