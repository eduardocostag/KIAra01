import { AutomationWorkspace } from "@/components/automation/automation-workspace"
import { requireWorkspace } from "@/lib/auth"

export const metadata = { title: "Kiara Automation" }

export default async function AutomationPage() {
  const { userId } = await requireWorkspace()
  return <AutomationWorkspace userId={userId} />
}
