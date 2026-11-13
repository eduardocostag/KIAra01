import { LogoutButton } from "@/components/auth/logout-button"
import { SettingsSectionNav } from "@/components/app-shell/workspace-section-nav"
import { requireWorkspace } from "@/lib/auth"

export default async function SettingsLayout({ children }: { children: React.ReactNode }) {
  const workspace = await requireWorkspace()
  return <div className="mx-auto w-full max-w-7xl space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-medium tracking-tight">Configurações</h1>
        <p className="mt-1 text-sm text-muted-foreground">Sua conta, sua operação e as integrações da Kiara.</p>
      </div>
      <LogoutButton />
    </header>
    <SettingsSectionNav isSystemAdmin={workspace.isSystemAdmin} />
    {children}
  </div>
}
