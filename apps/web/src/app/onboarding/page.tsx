import { OrganizationList } from "@clerk/nextjs"
import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"

export default async function OnboardingPage() {
  const session = await auth()
  if (!session.userId) redirect("/sign-in")
  if (session.orgId) redirect("/app")
  return <PremiumAuthShell eyebrow="Configuração inicial" title="Um espaço seguro para a sua operação." description="Leads, conversas, credenciais e permissões permanecem separados por empresa."><div className="flex justify-center"><OrganizationList afterCreateOrganizationUrl="/app" afterSelectOrganizationUrl="/app" hidePersonal skipInvitationScreen /></div></PremiumAuthShell>
}
