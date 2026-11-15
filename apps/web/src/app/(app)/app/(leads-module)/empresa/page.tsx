import { CompanyWorkspace } from "@/components/app-shell/company-workspace"

export default function CompanyPage() {
  return <div className="mx-auto w-full max-w-4xl space-y-6">
    <header>
      <h1 className="text-3xl font-medium tracking-tight">Minha empresa</h1>
      <p className="mt-1 text-sm text-muted-foreground">Ensine a Kiara sobre o seu negócio para ela vender e atender como alguém da sua equipe.</p>
    </header>
    <CompanyWorkspace />
  </div>
}
