"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  House,
  Inbox,
  Menu,
  Radar,
  Settings2,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { KiaraBrand } from "@/components/brand/kiara-brand";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/app/leads", label: "Visão geral", icon: House },
  { href: "/app/hunter", label: "Hunter", icon: UsersRound },
  { href: "/app/inbox", label: "Atendimento", icon: Inbox },
  { href: "/app/pipeline", label: "Leads e CRM", icon: Inbox },
  { href: "/app/concorrencia", label: "Concorrência", icon: Radar },
  { href: "/app/settings", label: "Configurações", icon: Settings2 },
];

function Navigation({
  onNavigate,
  isSystemAdmin,
}: {
  onNavigate?: () => void;
  isSystemAdmin: boolean;
}) {
  const pathname = usePathname();
  const items = isSystemAdmin
    ? [
        ...nav,
        { href: "/app/admin", label: "Administração", icon: ShieldCheck },
      ]
    : nav;
  return (
    <nav aria-label="Navegação principal" className="kiara-shell-nav space-y-2">
      {items.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/app" ? pathname === href
            : href === "/app/inbox" ? pathname.startsWith("/app/inbox") || pathname.startsWith("/app/followups")
              : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "kiara-shell-nav-link group relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-[13px] font-medium transition-all duration-200",
              active
                ? "is-active text-sidebar-accent-foreground"
                : "text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground",
            )}
          >
            <Icon
              className="kiara-shell-nav-icon size-[18px] shrink-0"
              strokeWidth={active ? 2.3 : 1.9}
              aria-hidden="true"
            />
            <span className="flex-1">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({
  children,
  isSystemAdmin = false,
}: {
  children: React.ReactNode;
  isSystemAdmin?: boolean;
}) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const isLeadsModule = pathname.startsWith("/app/leads") || 
                        pathname.startsWith("/app/hunter") || 
                        pathname.startsWith("/app/inbox") || 
                        pathname.startsWith("/app/pipeline") || 
                        pathname.startsWith("/app/concorrencia") || 
                        pathname.startsWith("/app/settings") || 
                        pathname.startsWith("/app/admin") ||
                        pathname.startsWith("/app/followups") ||
                        pathname.startsWith("/app/conteudo") ||
                        pathname.startsWith("/app/integrations");


  return (
    <div className="kiara-workspace min-h-screen bg-background text-foreground">
      <a href="#conteudo" className="skip-link">
        Pular para o conteúdo
      </a>
      
      {/* Sidebar Comercial apenas para Leads */}
      {isLeadsModule && (
        <aside className="kiara-sidebar fixed inset-y-0 left-0 z-30 hidden w-[202px] flex-col border-r border-sidebar-border bg-sidebar px-3 py-6 md:flex">
          <Link href="/app" className="kiara-shell-brand mb-8 flex min-h-12 items-center px-2" aria-label="Kiara, início">
            <KiaraBrand inverse />
          </Link>
          <Navigation isSystemAdmin={isSystemAdmin} />
          {isSystemAdmin ? <div className="kiara-shell-sidebar-footer mt-auto px-2 pt-5">
            <Link href="/app/platform" aria-label="Abrir plataforma KIARA" className="inline-flex min-h-11 items-center text-[10px] font-semibold tracking-[.18em] text-sidebar-foreground/60 hover:text-sidebar-foreground">
              Plataforma KIARA
            </Link>
          </div> : null}
        </aside>
      )}

      {/* Header simplificado para Plataforma/Selector */}
      {!isLeadsModule && pathname !== "/app" && (
        <header className="fixed top-0 left-0 z-30 flex w-full items-center border-b border-border bg-background/80 px-6 py-4 backdrop-blur-xl">
           <Link href="/app" className="flex items-center gap-2 font-medium text-muted-foreground hover:text-foreground">
             <Menu className="size-4" /> Voltar ao Início
           </Link>
        </header>
      )}

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="fixed left-4 top-4 z-40 size-11 rounded-xl bg-background/90 shadow-lg backdrop-blur-xl md:hidden"
            aria-label="Abrir menu"
          >
            <Menu />
          </Button>
        </SheetTrigger>
        <SheetContent
          side="left"
          className="flex w-72 flex-col border-sidebar-border bg-sidebar p-5 text-sidebar-foreground"
        >
          {/* Menu Mobile unificado */}
          <SheetHeader className="p-0 text-left">
            <SheetTitle>
              <KiaraBrand inverse />
            </SheetTitle>
          </SheetHeader>
          <div className="mt-7">
            <Navigation
              isSystemAdmin={isSystemAdmin}
              onNavigate={() => setMenuOpen(false)}
            />
            <Link href="/app/platform" onClick={() => setMenuOpen(false)} className="mt-6 block rounded-xl p-3 text-sm font-medium text-sidebar-foreground/60 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground">
              Plataforma KIARA
            </Link>
          </div>
        </SheetContent>
      </Sheet>
      <div className={cn("min-w-0", isLeadsModule && "md:pl-[202px]")}>
        <main
          id="conteudo"
          tabIndex={-1}
          className={cn(
            "relative mx-auto min-h-screen w-full min-w-0 max-w-[1540px] outline-none sm:p-7",
            isLeadsModule ? "p-4 pt-20 md:pt-7 lg:p-8" : "p-0"
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
