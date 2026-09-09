"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"
import { ArrowUpRight, ChevronRight, Gauge, Inbox, Menu, PanelsTopLeft, Plug, Search, Settings, ShieldCheck, Target, UsersRound } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { ThemeToggle } from "@/components/brand/theme-toggle"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

const nav = [
  { href: "/app", label: "Visão geral", icon: Gauge },
  { href: "/app/hunter", label: "Hunter", icon: Target },
  { href: "/app/pipeline", label: "Pipeline", icon: UsersRound },
  { href: "/app/inbox", label: "Inbox", icon: Inbox },
  { href: "/app/integrations", label: "Integrações", icon: Plug },
]

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  return <nav aria-label="Navegação principal" className="space-y-1">
    {nav.map(({ href, label, icon: Icon }) => {
      const active = href === "/app" ? pathname === href : pathname.startsWith(href)
      return <Link key={href} href={href} onClick={onNavigate} aria-current={active ? "page" : undefined} className={cn("group relative flex min-h-11 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition-colors", active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground")}>
        <Icon className={cn("size-4", active && "text-sidebar-primary")} aria-hidden="true" /><span className="flex-1">{label}</span>{active && <span className="size-1.5 rounded-full bg-sidebar-primary" aria-hidden="true" />}
      </Link>
    })}
  </nav>
}

function SidebarFooter({ onNavigate }: { onNavigate?: () => void }) {
  return <div className="mt-auto space-y-4 pt-8">
    <div className="rounded-lg border border-sidebar-border bg-sidebar-foreground/3 p-3.5"><p className="flex items-center gap-2 text-xs font-medium text-sidebar-foreground"><ShieldCheck className="size-4 text-sidebar-primary" />Você mantém o controle</p><p className="mt-2 text-[11px] leading-5 text-sidebar-foreground/60">Pesquise e organize seus leads. Mensagens externas exigem sua aprovação.</p></div>
    <Link href="/app/settings" onClick={onNavigate} className="flex min-h-11 items-center gap-3 border-t border-sidebar-border px-2 pt-3 text-xs font-medium text-sidebar-foreground/65 hover:text-sidebar-foreground"><Settings className="size-4" />Configurações<ArrowUpRight className="ml-auto size-3.5" /></Link>
  </div>
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const pathname = usePathname()
  const current = nav.find((item) => item.href !== "/app" && pathname.startsWith(item.href))?.label ?? (pathname.startsWith("/app/settings") ? "Configurações" : "Visão geral")
  return <div className="kiara-workspace min-h-screen bg-background text-foreground">
    <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar px-4 py-6 lg:flex">
      <Link href="/app" className="mb-9 flex min-h-10 items-center px-2" aria-label="Kiara, início"><KiaraBrand inverse /></Link>
      <p className="mb-3 px-3 text-[9px] font-semibold uppercase tracking-[.18em] text-sidebar-foreground/40">Workspace comercial</p>
      <Navigation />
      <SidebarFooter />
    </aside>
    <div className="min-w-0 lg:pl-60">
      <header className="app-shell-header sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur-sm sm:px-6 lg:px-8">
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger asChild><Button variant="ghost" size="icon" className="size-10 lg:hidden" aria-label="Abrir menu"><Menu /></Button></SheetTrigger>
          <SheetContent side="left" className="flex w-72 flex-col border-sidebar-border bg-sidebar p-5 text-sidebar-foreground">
            <SheetHeader className="p-0 text-left"><SheetTitle><KiaraBrand inverse /></SheetTitle><SheetDescription className="sr-only">Navegação do workspace comercial Kiara</SheetDescription></SheetHeader>
            <div className="mt-7"><Navigation onNavigate={() => setMenuOpen(false)} /></div><SidebarFooter onNavigate={() => setMenuOpen(false)} />
          </SheetContent>
        </Sheet>
        <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground"><PanelsTopLeft className="hidden size-4 sm:block" aria-hidden="true" /><span className="hidden sm:inline">Workspace</span><ChevronRight className="hidden size-3 sm:block" aria-hidden="true" /><span className="truncate font-medium text-foreground">{current}</span></div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <Button asChild variant="ghost" className="hidden h-9 gap-2 text-xs sm:inline-flex"><Link href="/app/hunter"><Search className="size-3.5" />Pesquisar leads</Link></Button>
          <span className="hidden h-4 w-px bg-border sm:block" aria-hidden="true" /><ThemeToggle />
          <Button asChild variant="outline" size="icon" className="size-9 rounded-lg"><Link href="/app/settings" aria-label="Configurações do workspace"><Settings className="size-4" /></Link></Button>
        </div>
      </header>
      <main id="conteudo" tabIndex={-1} className="mx-auto w-full min-w-0 max-w-[1600px] p-4 outline-none sm:p-6 lg:p-8">{children}</main>
    </div>
  </div>
}
