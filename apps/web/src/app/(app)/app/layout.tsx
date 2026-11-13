import { AppShell } from "@/components/app-shell/app-shell"
import { AdminAccessProvider } from "@/components/app-shell/admin-access"
import { AuthenticationRequiredError, requireWorkspace } from "@/lib/auth"
import { redirect } from "next/navigation"
import { ViewTransition } from "react"
import { FxPointer } from "@/components/fx/fx"
import "@/components/fx/effects.css"
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
  return <AdminAccessProvider allowed={isSystemAdmin}><AppShell isSystemAdmin={isSystemAdmin}><FxPointer /><ViewTransition default="fx-route">{children}</ViewTransition></AppShell></AdminAccessProvider>
}
