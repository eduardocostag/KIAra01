import { redirect } from "next/navigation"
import { AutomationWorkspace } from "@/components/automation/automation-workspace"
import { requireWorkspace } from "@/lib/auth"

export const metadata = { title: "Kiara Automation" }

export default async function AutomationPage() {
  const { userId, modules } = await requireWorkspace()
  if (!modules.includes("automation")) redirect("/app")  // the proxy redirects first; this is the backstop
  return <AutomationWorkspace userId={userId} />
}
