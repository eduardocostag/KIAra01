import { redirect } from "next/navigation"
import { PlatformOverview } from "@/components/platform/platform-overview"
import { PlatformUnavailable } from "@/components/platform/platform-unavailable"
import { getPlatformContext, PlatformApiError } from "@/lib/platform/server"

export default async function PlatformPage() {
  let context
  try { context = await getPlatformContext() }
  catch (error) {
    if (!(error instanceof PlatformApiError)) throw error
    if (error.status === 401) redirect("/sign-in")
    return <PlatformUnavailable denied={error.status === 403 || error.status === 404} requestId={error.requestId} />
  }
  return <PlatformOverview context={context} />
}
