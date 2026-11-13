import Link from "next/link";
import { ArrowRight, Inbox, MessageCircle, Search, Settings2, ShieldCheck, Workflow } from "lucide-react";
import { OrbitScene } from "@/components/brand/orbit-scene";
import { requireWorkspace } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default async function ModuleSelectorPage() {
  // The layout already enforces sign-in; here we only need to know whether to show Administração.
  const isSystemAdmin = await requireWorkspace().then((workspace) => workspace.isSystemAdmin).catch(() => false);
  const modules = [
    { href: "/app/leads", label: "KIARA Leads", description: "Pesquisa, CRM e Pipeline.", icon: Search, operational: true },
    { href: "/app/whatsapp", label: "KIARA WhatsApp", description: "Conexão, análise e automação.", icon: MessageCircle, operational: true },
    { href: "/app/chat", label: "KIARA Chat", description: "Conversa, voz e criação com IA.", icon: Inbox, operational: true },
    { href: "/app/automation", label: "KIARA Automation", description: "Fluxos, tarefas, agenda, redes e anúncios.", icon: Workflow, operational: true },
  ];
  const shortcuts = [
    { href: "/app/settings", label: "Configurações", icon: Settings2 },
    ...(isSystemAdmin ? [{ href: "/app/admin", label: "Administração", icon: ShieldCheck }] : []),
  ];

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center p-8">
      <div className="absolute inset-0 z-0 opacity-20">
        <OrbitScene />
      </div>
      <nav aria-label="Conta e administração" className="absolute right-4 top-4 z-20 flex gap-2 sm:right-8 sm:top-6">
        {shortcuts.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/10 bg-black/40 px-3.5 text-sm font-medium text-white/75 backdrop-blur-xl transition hover:border-primary/50 hover:text-white">
            <Icon className="size-4" aria-hidden="true" />{label}
          </Link>
        ))}
      </nav>
      <div className="relative z-10 w-full max-w-5xl text-center">
        <h1 className="mb-12 text-4xl font-bold tracking-tight">Selecione o módulo de operação</h1>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {modules.map(({ href, label, description, icon: Icon, operational }) => (
            <Link key={href} href={href} className={cn(
              "group relative flex flex-col items-center rounded-3xl border border-white/10 bg-black/40 p-8 backdrop-blur-xl transition-all hover:border-primary/50 hover:bg-black/60",
              !operational && "opacity-70 hover:opacity-100"
            )}>
              <div className="mb-6 rounded-2xl bg-white/5 p-4 text-primary transition-colors group-hover:bg-primary/20">
                <Icon className="size-10" />
              </div>
              <h2 className="mb-2 text-xl font-semibold">{label}</h2>
              <p className="mb-8 text-sm text-muted-foreground">{description}</p>

              {!operational && (
                <span className="mb-4 inline-block rounded-full bg-yellow-500/20 px-3 py-1 text-xs font-medium text-yellow-500">
                  Em preparação
                </span>
              )}

              <span className="mt-auto inline-flex min-h-10 w-full items-center justify-center rounded-lg text-sm font-medium group-hover:bg-primary group-hover:text-primary-foreground">
                Acessar <ArrowRight className="ml-2 size-4" />
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
