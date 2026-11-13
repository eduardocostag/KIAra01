import { ComingSoon } from "@/components/early-access/coming-soon"
import { requireWorkspace } from "@/lib/auth"

/** Early access: only the system administrator uses this module until launch. */
export default async function Layout({ children }: { children: React.ReactNode }) {
  const { isSystemAdmin } = await requireWorkspace()
  return isSystemAdmin ? children : <ComingSoon module="chat" />
}
