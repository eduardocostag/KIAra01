import { notFound, redirect } from "next/navigation"
import { AdminConsole } from "@/components/app-shell/admin-console"
import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth"
import { getAdminSnapshot } from "@/lib/admin/snapshot"

export const dynamic = "force-dynamic"

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ mailerfind?: string }> }) {
  try {
    await requireSystemAdmin()
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) redirect("/sign-in")
    if (error instanceof AdministratorRequiredError) notFound()
    throw error
  }
  const result = (await searchParams).mailerfind
  const mailerFindResult = result === "connected" || result === "denied" || result === "error" ? result : undefined
  return <div className="mx-auto w-full max-w-7xl"><AdminConsole initialSnapshot={await getAdminSnapshot()} mailerFindResult={mailerFindResult} /></div>
}
