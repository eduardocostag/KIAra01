import { TeamWorkspace } from "@/components/app-shell/team-plan"

export default function TeamPage() {
  return <div className="mx-auto w-full max-w-4xl space-y-6">
    <header><h1 className="text-3xl font-medium tracking-tight">Equipe</h1><p className="mt-1 text-sm text-muted-foreground">Convide vendedores: cada um entra com a própria conta e trabalha nos leads da empresa.</p></header>
    <TeamWorkspace />
  </div>
}
