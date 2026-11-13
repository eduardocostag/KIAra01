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
    { href: "/app/pipeline", label: "Contatos", icon: UsersRound },
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
  
  // Detecta o módulo ativo
  const modulePrefix = previewModule ?? modulePrefixForPath(pathname);
  const isModuleActive = !!modulePrefix && pathname !== '/app';
  const isWhatsApp = modulePrefix === "/app/whatsapp";
  const isChat = modulePrefix === "/app/chat";

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
            <KiaraBrand inverse />
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
        <SheetTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className={cn("fixed left-4 top-4 z-40 size-11 rounded-xl bg-background/90 shadow-lg backdrop-blur-xl md:hidden", !isModuleActive && "hidden")}
            aria-label="Abrir menu"
          >
            <Menu />
          </Button>
        </SheetTrigger>
        <SheetContent
          side="left"
          className={cn("flex w-72 flex-col border-sidebar-border bg-sidebar p-5 text-sidebar-foreground", isWhatsApp && "kiara-whatsapp-shell")}
        >
          {/* Menu Mobile unificado */}
          <SheetHeader className="p-0 text-left">
            <SheetTitle>
              <KiaraBrand inverse />
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
          </div>
        </SheetContent>
      </Sheet>
      <div className={cn("min-w-0", isModuleActive && "md:pl-[202px]")}>
        <main
          id="conteudo"
          tabIndex={-1}
          className={cn(
            "relative mx-auto min-h-screen w-full min-w-0 max-w-[1540px] outline-none sm:p-7",
            isModuleActive ? "p-4 pt-20 md:pt-7 lg:p-8" : pathname === "/app" ? "p-0 sm:p-0" : "px-4 pb-12 pt-24 sm:px-8 sm:pt-28"
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
