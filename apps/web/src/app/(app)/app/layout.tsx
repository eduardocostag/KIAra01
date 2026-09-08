import { AppShell } from "@/components/app-shell/app-shell"
import { requireWorkspace } from "@/lib/auth"

export default async function OperationalLayout({ children }: { children: React.ReactNode }) {
  await requireWorkspace()
  return <AppShell>{children}</AppShell>
}
