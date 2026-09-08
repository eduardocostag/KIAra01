"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Bell, Bot, ChevronDown, Gauge, MessageCircle as Instagram, Menu, Plug, Search, Settings, Target, UsersRound } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { ThemeToggle } from "@/components/brand/theme-toggle"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

const nav = [
  { href: "/app", label: "Visão geral", icon: Gauge },
  { href: "/app/inbox", label: "Inbox", icon: Instagram, badge: "3" },
  { href: "/app/hunter", label: "Hunter", icon: Target },
  { href: "/app/pipeline", label: "Pipeline", icon: UsersRound },
  { href: "/app/integrations", label: "Integrações", icon: Plug },
]

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  return <nav aria-label="Navegação principal" className="space-y-1">
    {nav.map(({ href, label, icon: Icon, badge }) => {
      const active = href === "/app" ? pathname === href : pathname.startsWith(href)
      return <Link key={href} href={href} onClick={onNavigate} aria-current={active ? "page" : undefined} className={cn("group relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-[background-color,color,transform] duration-150 hover:translate-x-px", active ? "bg-brand-subtle text-brand-subtle-foreground before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
        <Icon className="size-4" aria-hidden="true"/><span className="flex-1">{label}</span>{badge && <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", active ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground")}>{badge}</span>}
      </Link>
    })}
  </nav>
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-muted/25 text-foreground">
    <a href="#conteudo" className="sr-only z-50 rounded-md bg-background p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Pular para o conteúdo</a>
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r bg-sidebar/94 p-4 shadow-[8px_0_32px_oklch(0.1_0.03_267/0.04)] backdrop-blur-xl lg:flex lg:flex-col">
      <Link href="/app" className="mb-8 flex min-h-11 items-center gap-3 px-2" aria-label="Kiara, início">
        <KiaraBrand />
      </Link>
      <Navigation />
      <div className="mt-auto space-y-3">
        <div className="rounded-xl border bg-muted/35 p-3 text-xs leading-5 text-muted-foreground"><span className="mb-1 flex items-center gap-2 font-semibold text-foreground"><Bot className="size-4 text-primary"/>Autonomia nível 3</span>Toda mensagem externa exige aprovação humana.</div>
        <Link href="/app/settings" className="flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"><Settings className="size-4"/>Configurações</Link>
      </div>
    </aside>
    <div className="lg:pl-64">
      <header className="app-shell-header sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-background/82 px-4 backdrop-blur-xl sm:px-6">
        <Sheet>
          <SheetTrigger asChild><Button variant="ghost" size="icon" className="lg:hidden" aria-label="Abrir menu"><Menu/></Button></SheetTrigger>
          <SheetContent side="left" className="w-72 p-5"><SheetHeader><SheetTitle>Kiara</SheetTitle><SheetDescription>Lead Intelligence</SheetDescription></SheetHeader><div className="mt-7"><Navigation /></div></SheetContent>
        </Sheet>
        <div className="relative hidden max-w-sm flex-1 md:block"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"/><Input className="h-9 pl-9" placeholder="Buscar lead ou conversa" aria-label="Buscar lead ou conversa"/></div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" className="hidden max-w-52 sm:flex"><span className="size-2 rounded-full bg-success"/><span className="truncate">Studio Aurora</span><ChevronDown/></Button>
          <ThemeToggle />
          <Button variant="ghost" size="icon" aria-label="Notificações"><Bell/></Button>
          <div className="grid size-8 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary" aria-label="Usuário Eduardo">EG</div>
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-[1680px] p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  </div>
}
