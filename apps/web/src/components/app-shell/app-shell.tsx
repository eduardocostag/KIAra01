"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"
import { Bell, House, Inbox, Menu, PlugZap, Search, Settings2, UsersRound } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

const nav = [
  { href: "/app", label: "Visão geral", icon: House },
  { href: "/app/hunter", label: "Leads", icon: UsersRound },
  { href: "/app/inbox", label: "Inbox", icon: Inbox },
  { href: "/app/integrations", label: "Integrações", icon: PlugZap },
]

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  return <nav aria-label="Navegação principal" className="kiara-shell-nav space-y-2">
    {nav.map(({ href, label, icon: Icon }) => {
      const active = href === "/app" ? pathname === href : pathname.startsWith(href)
      return <Link key={href} href={href} onClick={onNavigate} aria-current={active ? "page" : undefined} className={cn("kiara-shell-nav-link group relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-[13px] font-medium transition-all duration-200", active ? "is-active text-sidebar-accent-foreground" : "text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground")}>
        <Icon className="kiara-shell-nav-icon size-[18px] shrink-0" strokeWidth={active ? 2.3 : 1.9} aria-hidden="true" /><span className="flex-1">{label}</span>
      </Link>
    })}
  </nav>
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const pathname = usePathname()
  const current = nav.find((item) => item.href !== "/app" && pathname.startsWith(item.href))?.label ?? "Visão geral"
  return <div className="kiara-workspace min-h-screen bg-background text-foreground">
    <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>
    <aside className="kiara-sidebar fixed inset-y-0 left-0 z-30 hidden w-[202px] flex-col border-r border-sidebar-border bg-sidebar px-3 py-6 md:flex">
      <Link href="/app" className="kiara-shell-brand mb-8 flex min-h-12 items-center px-2" aria-label="Kiara, início"><KiaraBrand inverse /></Link>
      <Navigation />
      <div className="kiara-shell-sidebar-footer mt-auto px-2 pt-5"><span className="text-[10px] font-semibold tracking-[.18em] text-sidebar-foreground/45">KIARA</span></div>
    </aside>
    <div className="min-w-0 pt-16 md:pl-[202px]">
      <header className="app-shell-header fixed inset-x-0 top-0 z-40 flex h-16 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur-xl sm:px-6 md:left-[202px] md:px-8">
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger asChild><Button variant="ghost" size="icon" className="size-10 md:hidden" aria-label="Abrir menu"><Menu /></Button></SheetTrigger>
          <SheetContent side="left" className="flex w-72 flex-col border-sidebar-border bg-sidebar p-5 text-sidebar-foreground">
            <SheetHeader className="p-0 text-left"><SheetTitle><KiaraBrand inverse /></SheetTitle><SheetDescription className="sr-only">Navegação do workspace comercial Kiara</SheetDescription></SheetHeader>
            <div className="mt-7"><Navigation onNavigate={() => setMenuOpen(false)} /></div>
            <div className="kiara-shell-sidebar-footer mt-auto px-2 pt-5"><span className="text-[10px] font-semibold tracking-[.18em] text-sidebar-foreground/45">KIARA</span></div>
          </SheetContent>
        </Sheet>
        <span className="truncate text-sm font-medium text-foreground/75 md:hidden">{current}</span>
        <div className="ml-auto flex shrink-0 items-center gap-3">
          <Link href="/app/hunter" className="kiara-shell-search hidden h-10 w-[280px] items-center gap-3 rounded-full px-4 text-xs text-muted-foreground sm:flex" aria-label="Pesquisar leads"><Search className="size-[17px]" aria-hidden="true" /><span>Pesquisar leads...</span></Link>
          <Link href="/app/inbox" className="kiara-shell-icon-button" aria-label="Abrir inbox de mensagens"><Bell className="size-[19px]" strokeWidth={1.9} aria-hidden="true" /></Link>
          <Link href="/app/settings" className="kiara-shell-icon-button" aria-label="Configurações do workspace"><Settings2 className="size-[20px]" strokeWidth={1.9} aria-hidden="true" /></Link>
        </div>
      </header>
      <main id="conteudo" tabIndex={-1} className="relative mx-auto w-full min-w-0 max-w-[1540px] p-4 outline-none sm:p-7 lg:p-10">{children}</main>
    </div>
  </div>
}
