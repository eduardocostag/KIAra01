import type { ReactNode } from "react"
import { Sparkles } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"

export function CopilotIntro({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <section className="kiara-copilot-stage kiara-soft-panel flex flex-col items-center px-6 py-8 text-center sm:flex-row sm:justify-between sm:text-left">
    <div className="flex flex-col items-center gap-5 sm:flex-row"><KiaraOrb size="md" active /><div><p className="flex items-center justify-center gap-2 text-[10px] font-semibold uppercase tracking-[.18em] text-primary sm:justify-start"><Sparkles className="size-3" />Kiara recomenda</p><h2 className="kiara-editorial mt-2 text-2xl font-medium tracking-tight">{title}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p></div></div>
    {action ? <div className="mt-5 shrink-0 sm:ml-6 sm:mt-0">{action}</div> : null}
  </section>
}
