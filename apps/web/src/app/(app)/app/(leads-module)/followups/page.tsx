import { WhatsAppGatewayWorkspace } from "@/components/app-shell/whatsapp-gateway-workspace"
import { SupportSectionNav } from "@/components/app-shell/workspace-section-nav"

export default async function FollowUpsPage() {
  return <div className="space-y-5"><SupportSectionNav /><WhatsAppGatewayWorkspace /></div>
}
