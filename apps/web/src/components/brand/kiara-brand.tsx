import { cn } from "@/lib/utils"
import { KSignal } from "./k-signal"

type KiaraBrandProps = {
  className?: string
  compact?: boolean
  inverse?: boolean
}

export function KiaraBrand({ className, compact = false, inverse = false }: KiaraBrandProps) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-3", className)}>
      <KSignal className={inverse ? "bg-white text-[#16152a]" : undefined} />
      {compact ? null : (
        <span className="min-w-0 leading-none">
          <span
            className={cn(
              "block text-[14px] font-semibold tracking-[0.11em]",
              inverse ? "text-white" : "text-foreground",
            )}
          >
            KIARA
          </span>
          <span
            className={cn(
              "mt-1 block truncate text-[10px] font-medium tracking-[0.02em]",
              inverse ? "text-white/58" : "text-muted-foreground",
            )}
          >
            Lead Intelligence
          </span>
        </span>
      )}
    </span>
  )
}
