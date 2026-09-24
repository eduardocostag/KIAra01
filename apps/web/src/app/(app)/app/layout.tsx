import { AppShell } from "@/components/app-shell/app-shell"
import { AuthenticationRequiredError, requireWorkspace } from "@/lib/auth"
import { redirect } from "next/navigation"
import "./reference-surfaces.css"
import "./orbit-dashboard.css"

export default async function OperationalLayout({ children }: { children: React.ReactNode }) {
  let isSystemAdmin = false
  try {
    const workspace = await requireWorkspace()
    isSystemAdmin = workspace.isSystemAdmin
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) redirect("/sign-in")
    throw error
  }
  return <AppShell isSystemAdmin={isSystemAdmin}>{children}</AppShell>
}
