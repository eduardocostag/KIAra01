import Link from "next/link";
import { Suspense } from "react";
import { ArrowRight, CheckCheck, Inbox, MessageCircle, Search, Settings2, ShieldCheck, Workflow } from "lucide-react";
import { OrbitScene } from "@/components/brand/orbit-scene";
import { LaunchBadge } from "@/components/early-access/launch-badge";
import { WelcomeTour, WelcomeTourLink } from "@/components/app-shell/welcome-tour";
import { kiaraApi } from "@/lib/api/server-client";
import { requireWorkspace } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default async function ModuleSelectorPage() {
  // The layout already enforces sign-in. Only WhatsApp is still early access (administrator only).
  const workspace = await requireWorkspace().catch(() => null);
  const isSystemAdmin = workspace?.isSystemAdmin ?? false;
  const modules = [
    { href: "/app/leads", label: "KIARA Leads", description: "Pesquisa, CRM e Pipeline.", icon: Search, operational: true },
    { href: "/app/whatsapp", label: "KIARA WhatsApp", description: "Conexão, análise e automação.", icon: MessageCircle, operational: isSystemAdmin },
    { href: "/app/chat", label: "KIARA Chat", description: "Conversa, voz e criação com IA.", icon: Inbox, operational: true },
    { href: "/app/automation", label: "KIARA Automation", description: "Fluxos, tarefas, agenda, redes e anúncios.", icon: Workflow, operational: true },
  ];
  // The pending approvals count streams in after the screen shows (PendingCount), so the modules never wait for the API.
  const shortcuts = [
    { href: "/app/aprovacoes", label: "Aprovações", icon: CheckCheck, count: true },
    { href: "/app/settings", label: "Configurações", icon: Settings2 },
    ...(isSystemAdmin ? [{ href: "/app/admin", label: "Administração", icon: ShieldCheck }] : []),
  ];

  return (
    <div className="relative flex min-h-[100dvh] flex-col items-center justify-start px-4 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-[calc(env(safe-area-inset-top)+4.25rem)] sm:min-h-screen sm:justify-center sm:p-8">
      <div className="absolute inset-x-0 top-0 z-0 h-72 bg-[radial-gradient(60%_100%_at_50%_0%,rgb(124_77_255/.35),transparent)] sm:hidden" aria-hidden="true" />
      <div className="absolute inset-0 z-0 hidden opacity-25 sm:block">
        <OrbitScene />
      </div>
      <nav aria-label="Conta e administração" className="absolute right-4 top-[calc(env(safe-area-inset-top)+.75rem)] z-20 flex gap-2 sm:right-8 sm:top-6">
        {shortcuts.map(({ href, label, icon: Icon, ...rest }) => {
          const count = "count" in rest;
          return (
          <Link key={href} href={href} aria-label={label} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/10 bg-black/40 px-3.5 text-sm font-medium text-white/75 backdrop-blur-xl transition hover:border-primary/50 hover:text-white">
            <Icon className="size-4" aria-hidden="true" /><span className="hidden sm:inline">{label}</span>
            {count ? <Suspense fallback={null}><PendingCount /></Suspense> : null}
          </Link>
          );
        })}
      </nav>
      <div className="relative z-10 mx-auto w-full max-w-md text-center md:max-w-5xl">
        <p className="fx-rise mb-3 text-[11px] font-semibold uppercase tracking-[.18em] text-primary sm:hidden">Kiara Intelligence</p><h1 className="fx-rise kiara-gradient-text mb-2 text-balance text-[1.75rem] font-bold leading-[1.05] tracking-tight sm:text-4xl">Selecione o módulo de operação</h1>
        <p className="fx-rise mb-6 text-sm text-muted-foreground sm:mb-9">Primeira vez aqui? <WelcomeTourLink className="-my-1.5 inline-block py-1.5 text-primary underline-offset-4 hover:underline" /></p>
        <div className="grid grid-cols-1 gap-3 sm:gap-6 md:grid-cols-2 lg:grid-cols-4">
          {modules.map(({ href, label, description, icon: Icon, operational }, index) => (
            <Link key={href} href={href} data-tilt="12" style={{ "--i": index + 1 } as React.CSSProperties} className={cn(
              "fx-rise fx-tilt fx-spot group relative grid grid-cols-[auto_1fr_auto] items-center gap-x-4 rounded-2xl border border-white/10 bg-black/50 p-4 text-left hover:border-primary/50 sm:bg-black/40 sm:backdrop-blur-xl hover:bg-black/60 sm:flex sm:flex-col sm:rounded-3xl sm:p-8 sm:text-center",
              operational && "kiara-module-live",
              !operational && "opacity-80 hover:opacity-100"
            )}>
              <div className="fx-pop kiara-halo-hover row-span-2 rounded-2xl bg-white/5 p-3 text-primary transition-colors group-hover:bg-primary/20 sm:mb-6 sm:p-4">
                <Icon className="size-7 sm:size-10" />
              </div>
              <h2 className="text-base font-semibold sm:mb-2 sm:text-xl">{label}</h2>
              <p className="col-start-2 text-[13px] text-muted-foreground sm:mb-8 sm:text-sm">{description}</p>

              {!operational && <span className="col-span-3 mt-3 flex justify-center sm:col-span-1 sm:mt-0 sm:block"><LaunchBadge /></span>}

              <span className="col-start-3 row-span-2 row-start-1 mt-auto inline-flex size-10 items-center justify-center rounded-full bg-white/5 text-sm font-medium group-hover:bg-primary group-hover:text-primary-foreground sm:min-h-10 sm:w-full sm:rounded-lg sm:bg-transparent">
                <span className="sr-only sm:not-sr-only">{operational ? "Acessar" : "Ver novidade"}</span> <ArrowRight className="size-4 sm:ml-2" />
              </span>
            </Link>
          ))}
        </div>
      </div>
      {workspace ? <WelcomeTour userId={workspace.userId} fullAccess /> : null}
    </div>
  );
}

/** Pending items in the approval center; nothing shows when there are none or the API is unavailable. */
async function PendingCount() {
  const pending = await kiaraApi("/v1/approvals?status=pending")
    .then(async (response) => (response.ok ? Number((await response.json()).pending) || 0 : 0))
    .catch(() => 0);
  if (!pending) return null;
  return <span aria-label={`${pending} pendente(s)`} className="grid min-w-5 place-items-center rounded-full bg-primary px-1.5 text-xs font-semibold tabular-nums text-primary-foreground">{pending > 99 ? "99+" : pending}</span>;
}
