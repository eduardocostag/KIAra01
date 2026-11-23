import { redirect } from "next/navigation"
import { requireWorkspace } from "@/lib/auth"

/** Only accounts the administrator gave KIARA WhatsApp (the proxy already redirects the others; this is the backstop). */
export default async function Layout({ children }: { children: React.ReactNode }) {
  const { modules } = await requireWorkspace()
  if (!modules.includes("whatsapp")) redirect("/app")
  return children
}
