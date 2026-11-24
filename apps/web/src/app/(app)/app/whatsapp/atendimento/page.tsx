import { ServiceSetupWorkspace } from "@/components/app-shell/service-setup"
import { WhatsAppSectionShell } from "@/components/app-shell/whatsapp-inbox"
import { requireWorkspace } from "@/lib/auth"

export const metadata = { title: "Configurar atendimento" }

export default async function ServiceSetupPage() {
  const { isSystemAdmin } = await requireWorkspace()
  return <WhatsAppSectionShell title="Configurar atendimento" isAdmin={isSystemAdmin}>
    <ServiceSetupWorkspace isAdmin={isSystemAdmin} />
  </WhatsAppSectionShell>
}
