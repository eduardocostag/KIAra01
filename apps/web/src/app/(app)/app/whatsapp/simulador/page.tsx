import { redirect } from "next/navigation"
import { SdrSimulator } from "@/components/app-shell/sdr-simulator"
import { requireWorkspace } from "@/lib/auth"

export const metadata = { title: "Simulador do WhatsApp" }

/** Test bench for the WhatsApp SDR, only for the system administrators. */
export default async function WhatsAppSimulatorPage() {
  const { isSystemAdmin } = await requireWorkspace()
  if (!isSystemAdmin) redirect("/app/whatsapp")
  return <SdrSimulator />
}
