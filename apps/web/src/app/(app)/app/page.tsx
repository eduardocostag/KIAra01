import Link from "next/link";
import { ArrowRight, Inbox, Radar, Search, ShieldCheck } from "lucide-react";
import { KiaraBrand } from "@/components/brand/kiara-brand";
import { OrbitScene } from "@/components/brand/orbit-scene";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function ModuleSelectorPage() {
  const modules = [
    { href: "/app/leads", label: "KIARA Leads", description: "Pesquisa, CRM e Pipeline.", icon: Search, operational: true },
    { href: "/app/platform/whatsapp", label: "KIARA WhatsApp", description: "Configurações de integração.", icon: Inbox, operational: false },
    { href: "/app/platform/atendimento", label: "KIARA Atendimento", description: "Gestão operacional.", icon: Inbox, operational: false },
    { href: "/app/platform/ti", label: "KIARA TI", description: "Suporte e infraestrutura.", icon: ShieldCheck, operational: false },
  ];

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center p-8">
      <div className="absolute inset-0 z-0 opacity-20">
        <OrbitScene />
      </div>
      <div className="relative z-10 w-full max-w-5xl text-center">
        <div className="mb-12 flex justify-center">
          <KiaraBrand />
        </div>
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
              
              <Button variant="ghost" className="mt-auto w-full group-hover:bg-primary group-hover:text-primary-foreground">
                Acessar <ArrowRight className="ml-2 size-4" />
              </Button>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
