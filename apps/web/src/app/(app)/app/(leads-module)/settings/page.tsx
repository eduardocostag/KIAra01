import { SettingsForm } from "@/components/app-shell/settings-form"
import { requireWorkspace } from "@/lib/auth"

export default async function SettingsPage() {
  // Identidade, Mensagens and Integrações are for the system administrators only.
  const { isSystemAdmin } = await requireWorkspace()
  return <div className="mx-auto w-full max-w-7xl"><SettingsForm fullAccess={isSystemAdmin} /></div>
}
