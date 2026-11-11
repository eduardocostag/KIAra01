import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { PlatformSkills } from "@/components/platform/platform-skills"
import { PlatformUnavailable } from "@/components/platform/platform-unavailable"
import type { PlatformSkill } from "@/lib/platform/contracts"
import { getPlatformSkills, PlatformApiError } from "@/lib/platform/server"

export const metadata: Metadata = {
  title: "Skills | Plataforma KIARA",
  description: "Catálogo de referências disponíveis para os módulos KIARA.",
}

export default async function PlatformSkillsPage() {
  let skills: readonly PlatformSkill[]
  try {
    skills = await getPlatformSkills()
  } catch (error) {
    if (!(error instanceof PlatformApiError)) throw error
    if (error.status === 401) redirect("/sign-in")
    return <PlatformUnavailable denied={error.status === 403 || error.status === 404} requestId={error.requestId} />
  }
  return <PlatformSkills skills={skills} />
}
