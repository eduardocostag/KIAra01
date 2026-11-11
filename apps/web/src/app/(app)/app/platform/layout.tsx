import type { Metadata } from "next"
import type { ReactNode } from "react"
import { redirect } from "next/navigation"
import { requireWorkspace } from "@/lib/auth"
import { PlatformShell } from "@/components/platform/platform-shell"
import { PlatformUnavailable } from "@/components/platform/platform-unavailable"
import { getPlatformContext, PlatformApiError } from "@/lib/platform/server"

export const metadata: Metadata = { title: "Plataforma KIARA", description: "Módulos e acessos da plataforma KIARA para sua empresa." }

export default async function PlatformLayout({ children }: { children: ReactNode }) {
  const workspace = await requireWorkspace()
  if (!workspace.isSystemAdmin) return <PlatformUnavailable denied />

  let context
  try { context = await getPlatformContext() }
  catch (error) {
    if (!(error instanceof PlatformApiError)) throw error
    if (error.status === 401) redirect("/sign-in")
    return <PlatformUnavailable denied={error.status === 403 || error.status === 404} requestId={error.requestId} />
  }
  return <PlatformShell context={context}>{children}</PlatformShell>
}
