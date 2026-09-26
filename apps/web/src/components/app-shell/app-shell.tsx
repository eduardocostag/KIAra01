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
  { href: "/app", label: "Visão geral", icon: House },
  { href: "/app/hunter", label: "Hunter", icon: UsersRound },
  { href: "/app/inbox", label: "Leads", icon: Inbox },
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
          href === "/app" ? pathname === href : pathname.startsWith(href);
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
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="kiara-workspace min-h-screen bg-background text-foreground">
      <a href="#conteudo" className="skip-link">
        Pular para o conteúdo
      </a>
      <aside className="kiara-sidebar fixed inset-y-0 left-0 z-30 hidden w-[202px] flex-col border-r border-sidebar-border bg-sidebar px-3 py-6 md:flex">
        <Link
          href="/app"
          className="kiara-shell-brand mb-8 flex min-h-12 items-center px-2"
          aria-label="Kiara, início"
        >
          <KiaraBrand inverse />
        </Link>
        <Navigation isSystemAdmin={isSystemAdmin} />
        <div className="kiara-shell-sidebar-footer mt-auto px-2 pt-5">
          <span className="text-[10px] font-semibold tracking-[.18em] text-sidebar-foreground/45">
            KIARA
          </span>
        </div>
      </aside>
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
          <SheetHeader className="p-0 text-left">
            <SheetTitle>
              <KiaraBrand inverse />
            </SheetTitle>
            <SheetDescription className="sr-only">
              Navegação do workspace comercial Kiara
            </SheetDescription>
          </SheetHeader>
          <div className="mt-7">
            <Navigation
              isSystemAdmin={isSystemAdmin}
              onNavigate={() => setMenuOpen(false)}
            />
          </div>
          <div className="kiara-shell-sidebar-footer mt-auto px-2 pt-5">
            <span className="text-[10px] font-semibold tracking-[.18em] text-sidebar-foreground/45">
              KIARA
            </span>
          </div>
        </SheetContent>
      </Sheet>
      <div className="min-w-0 md:pl-[202px]">
        <main
          id="conteudo"
          tabIndex={-1}
          className="relative mx-auto min-h-screen w-full min-w-0 max-w-[1540px] p-4 pt-20 outline-none sm:p-7 sm:pt-20 md:pt-7 lg:p-8"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
