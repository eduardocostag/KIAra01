"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import {
  House,
  Inbox,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  UsersRound,
  ArrowLeft,
  Cable,
  MessageCircle,
  ScanText,
  Workflow,
  Sparkles,
  SlidersHorizontal,
  ListChecks,
  ScanLine,
  Building2,
  Ellipsis,
  Download,
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
import { InstallApp, openInstallApp, useCanInstall } from "@/components/app-shell/install-app";
import { isModuleNavActive, modulePrefixForPath } from "@/lib/module-navigation";

function subscribeHash(listener: () => void) {
  window.addEventListener("hashchange", listener);
  window.addEventListener("popstate", listener);
  return () => {
    window.removeEventListener("hashchange", listener);
    window.removeEventListener("popstate", listener);
  };
}

function currentHash() { return window.location.hash; }
function emptyHash() { return ""; }

const navConfigs = {
  "/app/leads": [
    { href: "/app/leads", label: "Visão geral", icon: House },
    { href: "/app/hunter", label: "Buscar leads", icon: Search },
    { href: "/app/presencial", label: "Presencial", icon: ScanLine },
    { href: "/app/fila", label: "Fila de hoje", icon: ListChecks },
    { href: "/app/pipeline", label: "Contatos", icon: UsersRound },
    { href: "/app/empresa", label: "Minha empresa", icon: Building2 },
  ],
  "/app/whatsapp": [
    { href: "/app/whatsapp", label: "Visão geral", icon: House },
    { href: "/app/whatsapp#conexao", label: "Conexão", icon: Cable },
    { href: "/app/whatsapp#analise", label: "Análise da conversa", icon: ScanText },
    { href: "/app/whatsapp/automacao", label: "Automação e contatos", icon: Workflow },
    { href: "/app/inbox", label: "Caixa de entrada", icon: Inbox },
    { href: "/app/whatsapp#configuracoes", label: "Configuração local", icon: Settings2 },
  ],
  "/app/atendimento": [
    { href: "/app/atendimento/inbox", label: "Inbox Unificado", icon: Inbox },
    { href: "/app/atendimento/followups", label: "Follow-ups", icon: UsersRound },
  ],
  "/app/chat": [
    { href: "/app/chat", label: "Conversa", icon: MessageCircle },
    { href: "/app/chat#capacidades", label: "Recursos e conexões", icon: Sparkles },
    { href: "/app/chat#configuracoes", label: "Preferências", icon: SlidersHorizontal },
    { href: "/app/inbox", label: "Caixa de entrada", icon: Inbox },
    { href: "/app/whatsapp", label: "WhatsApp", icon: Cable },
  ],
  "/app/ti": [
    { href: "/app/ti/logs", label: "Logs do Sistema", icon: ShieldCheck },
    { href: "/app/ti/config", label: "Infraestrutura", icon: Settings2 },
  ]
};

function Navigation({
  onNavigate,
  modulePrefix,
}: {
  onNavigate?: () => void;
  modulePrefix: string;
}) {
  const pathname = usePathname();
  const hash = useSyncExternalStore(subscribeHash, currentHash, emptyHash);
  const items = navConfigs[modulePrefix as keyof typeof navConfigs] || [];


  return (
    <nav aria-label="Navegação do módulo" className="kiara-shell-nav space-y-2">
      {items.map(({ href, label, icon: Icon }) => {
        const active = isModuleNavActive(pathname, hash, href);
        const NavigationLink = href.includes("#") ? "a" : Link;
        return (
          <NavigationLink
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
            <Icon className="size-[18px] shrink-0" strokeWidth={active ? 2.3 : 1.9} aria-hidden="true" />
            <span className="flex-1">{label}</span>
          </NavigationLink>
        );
      })}
    </nav>
  );
}

const TAB_LABELS: Record<string, string> = { "Visão geral": "Início", "Buscar leads": "Buscar", "Fila de hoje": "Hoje", "Análise da conversa": "Análise", "Automação e contatos": "Automação", "Caixa de entrada": "Entrada", "Inbox Unificado": "Inbox", "Logs do Sistema": "Logs" };

/** Mobile only: the module's first four sections as an app-style tab bar, plus "Mais" for the rest. */
function MobileTabBar({ modulePrefix, onMore }: { modulePrefix: string; onMore: () => void }) {
  const pathname = usePathname();
  const hash = useSyncExternalStore(subscribeHash, currentHash, emptyHash);
  const items = navConfigs[modulePrefix as keyof typeof navConfigs] || [];
  const primary = items.slice(0, 4);
  const moreActive = items.slice(4).some(({ href }) => isModuleNavActive(pathname, hash, href));
  if (!items.length) return null;
  return (
    <nav aria-label="Atalhos do módulo" className="kiara-tabbar md:hidden">
      {primary.map(({ href, label, icon: Icon }) => {
        const active = isModuleNavActive(pathname, hash, href);
        const TabLink = href.includes("#") ? "a" : Link;
        return (
          <TabLink key={href} href={href} aria-current={active ? "page" : undefined} className={cn("kiara-tab", active && "is-active")}>
            <span className="kiara-tab-icon"><Icon className="size-[19px]" strokeWidth={active ? 2.3 : 1.9} aria-hidden="true" /></span>
            <span className="kiara-tab-label">{TAB_LABELS[label] ?? label}</span>
          </TabLink>
        );
      })}
      {items.length > 4 ? (
        <button type="button" onClick={onMore} className={cn("kiara-tab", moreActive && "is-active")} aria-label="Mais opções do módulo">
          <span className="kiara-tab-icon"><Ellipsis className="size-[19px]" aria-hidden="true" /></span>
          <span className="kiara-tab-label">Mais</span>
        </button>
      ) : null}
    </nav>
  );
}

function useCurrentLabel(modulePrefix: string | null) {
  const pathname = usePathname();
  const hash = useSyncExternalStore(subscribeHash, currentHash, emptyHash);
  const items = modulePrefix ? navConfigs[modulePrefix as keyof typeof navConfigs] || [] : [];
  return items.find(({ href }) => isModuleNavActive(pathname, hash, href))?.label ?? "Kiara";
}

export function AppShell({
  children,
  previewModule,
}: {
  children: React.ReactNode;
  /** Kept for callers; Administração is now reached from the module selector. */
  isSystemAdmin?: boolean;
  /** Development preview only: render a module's sidebar outside its real route. */
  previewModule?: string;
}) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const canInstall = useCanInstall();
  
  // Detecta o módulo ativo
  const modulePrefix = previewModule ?? modulePrefixForPath(pathname);
  const isModuleActive = !!modulePrefix && pathname !== '/app';
  const isWhatsApp = modulePrefix === "/app/whatsapp";
  const isChat = modulePrefix === "/app/chat";
  const currentLabel = useCurrentLabel(modulePrefix);

  // Conversation and automation modules render their own full-height shell (ImmersiveShell).
  if (isWhatsApp || isChat || modulePrefix === "/app/automation") {
    return <div className="kiara-workspace min-h-dvh bg-background text-foreground">{children}</div>;
  }


  return (
    <div className={cn("kiara-workspace min-h-screen bg-background text-foreground", isWhatsApp && "kiara-whatsapp-shell")}>
      <a href="#conteudo" className="skip-link">
        Pular para o conteúdo
      </a>
      
      {/* Sidebar Modular */}
      {isModuleActive && (
        <aside className="kiara-sidebar fixed inset-y-0 left-0 z-30 hidden w-[202px] flex-col border-r border-sidebar-border bg-sidebar px-3 py-6 md:flex">
          <Link href="/app" className="kiara-shell-brand mb-8 flex min-h-12 items-center px-2" aria-label="Kiara, início">
            <KiaraBrand inverse scope={modulePrefix === "/app/leads" ? "leads" : "platform"} />
          </Link>
          {isWhatsApp && <div className="mb-5 flex items-center gap-2 rounded-xl border border-emerald-400/15 bg-emerald-400/5 px-3 py-3 text-sm font-semibold text-emerald-300"><MessageCircle className="size-4" aria-hidden="true" />WhatsApp</div>}
          {isChat && <div className="mb-5 flex items-center gap-2 rounded-xl border border-violet-400/20 bg-violet-400/5 px-3 py-3 text-sm font-semibold text-violet-200"><Sparkles className="size-4" aria-hidden="true" />KIARA Chat</div>}
          <Navigation modulePrefix={modulePrefix!} />
          <div className="kiara-shell-sidebar-footer mt-auto px-2 pt-5">
            {isWhatsApp && <p className="mb-3 text-xs leading-5 text-sidebar-foreground/60">Conexão e análise local.<br />Automação em área própria.</p>}
            {isChat && <p className="mb-3 text-xs leading-5 text-sidebar-foreground/60">Converse, crie e planeje.<br />Recursos conforme conexão.</p>}
            <Link href="/app" className="inline-flex min-h-11 items-center gap-2 text-xs font-medium text-sidebar-foreground/65 hover:text-sidebar-foreground"><ArrowLeft className="size-4" aria-hidden="true" />Trocar módulo</Link>
          </div>
        </aside>
      )}

      {/* Pages outside a module (settings, administration, platform): simple top bar back to the modules. */}
      {!isModuleActive && pathname !== "/app" && (
        <header className="fixed top-0 left-0 z-30 flex w-full items-center gap-4 border-b border-border bg-background/80 px-5 py-3 backdrop-blur-xl sm:px-8">
           <Link href="/app" className="flex min-h-10 items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
             <ArrowLeft className="size-4" aria-hidden="true" /> Módulos
           </Link>
           <span className="ml-auto"><KiaraBrand inverse /></span>
        </header>
      )}

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        {isModuleActive ? (
          <header className="kiara-mobile-bar md:hidden">
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="size-10 rounded-xl" aria-label="Abrir menu">
                <Menu />
              </Button>
            </SheetTrigger>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-primary/90">{modulePrefix === "/app/leads" ? "Kiara Leads" : "Kiara"}</p>
              <p className="truncate text-[15px] font-semibold leading-tight">{currentLabel}</p>
            </div>
            <Link href="/app" aria-label="Trocar módulo" className="kiara-mobile-orb"><span className="kiara-orb kiara-orb-sm" aria-hidden="true" /></Link>
          </header>
        ) : null}
        <SheetContent
          side="left"
          className={cn("flex w-72 flex-col border-sidebar-border bg-sidebar p-5 text-sidebar-foreground", isWhatsApp && "kiara-whatsapp-shell")}
        >
          {/* Menu Mobile unificado */}
          <SheetHeader className="p-0 text-left">
            <SheetTitle>
              <KiaraBrand inverse scope={modulePrefix === "/app/leads" ? "leads" : "platform"} />
            </SheetTitle>
            <SheetDescription>{isWhatsApp ? "WhatsApp · conexão, análise e automação" : isChat ? "KIARA Chat · conversa e criação" : "Navegue pelas áreas da Kiara"}</SheetDescription>
          </SheetHeader>
          <div className="mt-7">
            {isModuleActive && (
                <Navigation
                    modulePrefix={modulePrefix!}
                    onNavigate={() => setMenuOpen(false)}
                />
            )}
            <Link href="/app" onClick={() => setMenuOpen(false)} className="mt-6 block rounded-xl p-3 text-sm font-medium text-sidebar-foreground/60 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground">
              Trocar módulo
            </Link>
            {canInstall && (
              <button type="button" onClick={() => { setMenuOpen(false); openInstallApp(); }} className="mt-1 flex w-full items-center gap-2 rounded-xl p-3 text-left text-sm font-medium text-sidebar-foreground/60 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground">
                <Download className="size-4" aria-hidden="true" />Instalar app no celular
              </button>
            )}
          </div>
        </SheetContent>
      </Sheet>
      {isModuleActive ? <MobileTabBar modulePrefix={modulePrefix!} onMore={() => setMenuOpen(true)} /> : null}
      <div className={cn("min-w-0", isModuleActive && "md:pl-[202px]")}>
        <main
          id="conteudo"
          tabIndex={-1}
          className={cn(
            "relative mx-auto min-h-screen w-full min-w-0 max-w-[1540px] outline-none sm:p-7",
            isModuleActive ? "kiara-mobile-main p-4 pt-[76px] md:pt-7 lg:p-8" : pathname === "/app" ? "p-0 sm:p-0" : "px-4 pb-12 pt-24 sm:px-8 sm:pt-28"
          )}
        >
          {children}
        </main>
      </div>
      <InstallApp aboveTabBar={isModuleActive} />
    </div>
  );
}
