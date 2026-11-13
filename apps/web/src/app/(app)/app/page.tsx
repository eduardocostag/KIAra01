import Link from "next/link";
import { ArrowRight, CheckCheck, Inbox, MessageCircle, Search, Settings2, ShieldCheck, Workflow } from "lucide-react";
import { OrbitScene } from "@/components/brand/orbit-scene";
import { LaunchBadge } from "@/components/early-access/launch-badge";
import { kiaraApi } from "@/lib/api/server-client";
import { requireWorkspace } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default async function ModuleSelectorPage() {
  // The layout already enforces sign-in. WhatsApp, Chat and Automation are early access (administrator only).
  const isSystemAdmin = await requireWorkspace().then((workspace) => workspace.isSystemAdmin).catch(() => false);
  const modules = [
    { href: "/app/leads", label: "KIARA Leads", description: "Pesquisa, CRM e Pipeline.", icon: Search, operational: true },
    { href: "/app/whatsapp", label: "KIARA WhatsApp", description: "Conexão, análise e automação.", icon: MessageCircle, operational: isSystemAdmin },
    { href: "/app/chat", label: "KIARA Chat", description: "Conversa, voz e criação com IA.", icon: Inbox, operational: isSystemAdmin },
    { href: "/app/automation", label: "KIARA Automation", description: "Fluxos, tarefas, agenda, redes e anúncios.", icon: Workflow, operational: isSystemAdmin },
  ];
  // Pending items in the approval center; the page still renders if the API is unavailable.
  const pending = await kiaraApi("/v1/approvals?status=pending")
    .then(async (response) => (response.ok ? Number((await response.json()).pending) || 0 : 0))
    .catch(() => 0);
  const shortcuts = [
    { href: "/app/aprovacoes", label: "Aprovações", icon: CheckCheck, count: pending },
    { href: "/app/settings", label: "Configurações", icon: Settings2 },
    ...(isSystemAdmin ? [{ href: "/app/admin", label: "Administração", icon: ShieldCheck }] : []),
  ];

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center p-8">
      <div className="absolute inset-0 z-0 opacity-25">
        <OrbitScene />
      </div>
      <nav aria-label="Conta e administração" className="absolute right-4 top-4 z-20 flex gap-2 sm:right-8 sm:top-6">
        {shortcuts.map(({ href, label, icon: Icon, ...rest }) => {
          const count = "count" in rest ? Number(rest.count) : 0;
          return (
          <Link key={href} href={href} aria-label={count ? `${label}: ${count} pendente(s)` : label} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/10 bg-black/40 px-3.5 text-sm font-medium text-white/75 backdrop-blur-xl transition hover:border-primary/50 hover:text-white">
            <Icon className="size-4" aria-hidden="true" /><span className="hidden sm:inline">{label}</span>
            {count ? <span className="grid min-w-5 place-items-center rounded-full bg-primary px-1.5 text-xs font-semibold tabular-nums text-primary-foreground">{count > 99 ? "99+" : count}</span> : null}
          </Link>
          );
        })}
      </nav>
      <div className="relative z-10 w-full max-w-5xl text-center">
        <h1 className="fx-rise kiara-gradient-text mb-12 text-4xl font-bold tracking-tight">Selecione o módulo de operação</h1>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {modules.map(({ href, label, description, icon: Icon, operational }, index) => (
            <Link key={href} href={href} data-tilt="12" style={{ "--i": index + 1 } as React.CSSProperties} className={cn(
              "fx-rise fx-tilt fx-spot group relative flex flex-col items-center rounded-3xl border border-white/10 bg-black/40 p-8 backdrop-blur-xl hover:border-primary/50 hover:bg-black/60",
              !operational && "opacity-80 hover:opacity-100"
            )}>
              <div className="fx-pop kiara-halo-hover mb-6 rounded-2xl bg-white/5 p-4 text-primary transition-colors group-hover:bg-primary/20">
                <Icon className="size-10" />
              </div>
              <h2 className="mb-2 text-xl font-semibold">{label}</h2>
              <p className="mb-8 text-sm text-muted-foreground">{description}</p>

              {!operational && <LaunchBadge />}

              <span className="mt-auto inline-flex min-h-10 w-full items-center justify-center rounded-lg text-sm font-medium group-hover:bg-primary group-hover:text-primary-foreground">
                {operational ? "Acessar" : "Ver novidade"} <ArrowRight className="ml-2 size-4" />
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
