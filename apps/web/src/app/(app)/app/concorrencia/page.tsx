import type { Metadata } from "next"
import { notFound, redirect } from "next/navigation"
import { CompetitionConsole } from "@/components/competition/competition-console"
import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth"

export const metadata: Metadata = {
  title: "Concorrência | Kiara",
  description: "Análise própria de audiências públicas de concorrentes, com arquivo seguro na Kiara.",
}

export const dynamic = "force-dynamic"

export default async function CompetitionPage() {
  try {
    await requireSystemAdmin()
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) redirect("/sign-in")
    if (error instanceof AdministratorRequiredError) notFound()
    throw error
  }
  return <CompetitionConsole />
}
