import Link from "next/link";
import { Suspense } from "react";
import { CheckCheck, Settings2, ShieldCheck } from "lucide-react";
import { OrbitScene } from "@/components/brand/orbit-scene";
import { ModuleChoice } from "@/components/app-shell/module-choice";
import { WelcomeTour } from "@/components/app-shell/welcome-tour";
import { kiaraApi } from "@/lib/api/server-client";
import { requireWorkspace } from "@/lib/auth";
import { MODULES } from "@/lib/modules";

export default async function ModuleSelectorPage() {
  // The layout already enforces sign-in. Each account sees only the modules the administrator gave it.
  const workspace = await requireWorkspace().catch(() => null);
  const isSystemAdmin = workspace?.isSystemAdmin ?? false;
  const allowed = new Set(workspace?.modules ?? []);
  const modules = MODULES.filter(({ key }) => allowed.has(key));
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
      <ModuleChoice modules={modules} />
      {workspace ? <WelcomeTour userId={workspace.userId} modules={workspace.modules} /> : null}
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
