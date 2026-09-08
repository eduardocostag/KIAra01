import { Check, MessageCircle, Radar, ShieldCheck, StepForward } from "lucide-react"
import { cn } from "@/lib/utils"

const defaultSteps = [
  { label: "DM", detail: "Recebida", icon: MessageCircle },
  { label: "Insight", detail: "Contexto lido", icon: Radar },
  { label: "Revisão", detail: "Controle humano", icon: ShieldCheck },
  { label: "Ação", detail: "Próximo passo", icon: StepForward },
]

type SignalTrailProps = {
  className?: string
  compact?: boolean
  completedThrough?: number
  steps?: typeof defaultSteps
}

export function SignalTrail({
  className,
  compact = false,
  completedThrough = 1,
  steps = defaultSteps,
}: SignalTrailProps) {
  return (
    <ol
      className={cn(
        "signal-trail grid gap-0",
        compact ? "grid-cols-4" : "grid-cols-1 sm:grid-cols-4",
        className,
      )}
      aria-label="Trilha Kiara"
    >
      {steps.map(({ label, detail, icon: Icon }, index) => {
        const complete = index <= completedThrough
        const current = index === completedThrough + 1
        return (
          <li
            key={label}
            className={cn(
              "signal-trail-step relative flex min-w-0 items-center gap-3 pb-5 sm:block sm:pb-0",
              compact && "block pb-0",
            )}
            aria-current={current ? "step" : undefined}
          >
            <span
              className={cn(
                "relative z-10 grid size-8 shrink-0 place-items-center rounded-full border transition-colors",
                complete && "border-primary bg-primary text-primary-foreground",
                current && "border-primary bg-background text-primary ring-4 ring-primary/12",
                !complete && !current && "border-border bg-background text-muted-foreground",
              )}
            >
              {complete ? <Check className="size-3.5" strokeWidth={2} /> : <Icon className="size-3.5" strokeWidth={1.75} />}
            </span>
            <span className={cn("min-w-0", compact ? "mt-2 block" : "sm:mt-3 sm:block")}>
              <span className="block truncate text-[11px] font-semibold tracking-[-0.01em]">{label}</span>
              <span className={cn("mt-0.5 block text-[10px] leading-4 text-muted-foreground", compact && "hidden sm:block")}>{detail}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
