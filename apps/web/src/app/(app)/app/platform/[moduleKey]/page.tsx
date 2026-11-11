import { notFound, redirect } from "next/navigation"
import { ModulePreparation } from "@/components/platform/module-preparation"
import { PlatformUnavailable } from "@/components/platform/platform-unavailable"
import { isModuleKey } from "@/lib/platform/contracts"
import { getPlatformModule, PlatformApiError } from "@/lib/platform/server"

export default async function PlatformModulePage({ params }: { params: Promise<{ moduleKey: string }> }) {
  const { moduleKey } = await params
  if (!isModuleKey(moduleKey)) notFound()
  let detail
  try { detail = await getPlatformModule(moduleKey) }
  catch (error) {
    if (!(error instanceof PlatformApiError)) throw error
    if (error.status === 401) redirect("/sign-in")
    if (error.status === 404) notFound()
    return <PlatformUnavailable denied={error.status === 403} requestId={error.requestId} />
  }
  if (detail.module.key === "leads") redirect("/app")
  return <ModulePreparation module={detail.module} />
}
