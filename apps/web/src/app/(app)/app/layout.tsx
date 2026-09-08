import { AppShell } from "@/components/app-shell/app-shell"
import { ActiveWorkspaceRequiredError, AuthenticationRequiredError, requireWorkspace } from "@/lib/auth"
import { redirect } from "next/navigation"

export default async function OperationalLayout({ children }: { children: React.ReactNode }) {
  try {
    await requireWorkspace()
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) redirect("/sign-in")
    if (error instanceof ActiveWorkspaceRequiredError) redirect("/onboarding")
    throw error
  }
  return <AppShell>{children}</AppShell>
}
