"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Cable, MessageCircle, MessagesSquare, Settings2 } from "lucide-react"
import { cn } from "@/lib/utils"

function SectionLink({ href, label, active, icon: Icon }: {
  href: string
  label: string
  active: boolean
  icon: typeof MessageCircle
}) {
  return <Link
    href={href}
    aria-current={active ? "page" : undefined}
    className={cn(
      "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-medium transition-colors",
      active ? "border-primary/30 bg-primary/10 text-foreground" : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
    )}
  >
    <Icon className="size-4" aria-hidden="true" />
    {label}
  </Link>
}

export function SupportSectionNav() {
  const pathname = usePathname()
  const onInbox = pathname.startsWith("/app/inbox")

  return <nav aria-label="Seções de atendimento" className="flex flex-wrap gap-2">
    <SectionLink href="/app/inbox" label="Caixa de entrada" active={onInbox} icon={MessagesSquare} />
    <SectionLink href="/app/whatsapp" label="WhatsApp" active={!onInbox} icon={MessageCircle} />
  </nav>
}

export function SettingsSectionNav({ isSystemAdmin = false }: { isSystemAdmin?: boolean }) {
  const pathname = usePathname()
  const onIntegrations = pathname.startsWith("/app/settings/integrations")

  return <nav aria-label="Seções de configurações" className="flex flex-wrap gap-2">
    <SectionLink href="/app/settings" label="Geral" active={!onIntegrations} icon={Settings2} />
    {isSystemAdmin ? <SectionLink href="/app/settings/integrations" label="Integrações" active={onIntegrations} icon={Cable} /> : null}
  </nav>
}
