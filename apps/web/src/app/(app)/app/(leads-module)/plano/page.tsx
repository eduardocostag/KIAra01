import { PlanWorkspace } from "@/components/app-shell/team-plan"

export default function PlanPage() {
  return <div className="mx-auto w-full max-w-5xl space-y-6">
    <header><h1 className="text-3xl font-medium tracking-tight">Plano e uso</h1><p className="mt-1 text-sm text-muted-foreground">Quanto do seu plano você já usou neste mês.</p></header>
    <PlanWorkspace />
  </div>
}
