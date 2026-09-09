import { cn } from "@/lib/utils"

export function KiaraOrb({ className, size = "md", active = false }: { className?: string; size?: "sm" | "md" | "lg"; active?: boolean }) {
  return <span className={cn("kiara-orb", `kiara-orb-${size}`, active && "kiara-orb-active", className)} aria-hidden="true"><span className="kiara-orb-face"><i /><i /></span></span>
}
