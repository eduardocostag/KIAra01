import Link from "next/link";
import { ArrowRight, Inbox, LayoutGrid, LockKeyhole, MessageCircle, Search, Workflow } from "lucide-react";
import { WelcomeTourLink } from "@/components/app-shell/welcome-tour";
import { type ModuleInfo } from "@/lib/modules";
import { cn } from "@/lib/utils";

const ICONS: Record<string, typeof Search> = { leads: Search, whatsapp: MessageCircle, chat: Inbox, automation: Workflow };

/** The layout follows how many modules the account has: one centred card, two or three side by side, four in a row
 *  on wide screens; five or more wrap in rows of two (tablet) and three or four (desktop) with the last row centred. */
export function gridFor(count: number): { width: string; columns: string; card: string } {
  if (count <= 1) return { width: "md:max-w-md", columns: "grid", card: "" };
  if (count === 2) return { width: "md:max-w-3xl", columns: "grid md:grid-cols-2", card: "" };
  if (count === 3) return { width: "md:max-w-5xl", columns: "grid md:grid-cols-3", card: "" };
  if (count === 4) return { width: "md:max-w-6xl", columns: "grid md:grid-cols-2 lg:grid-cols-4", card: "" };
  const perRow = count === 5 || count === 6 || count === 9 ? 3 : 4;
  return {
    width: perRow === 3 ? "md:max-w-5xl" : "md:max-w-6xl",
    columns: "grid md:flex md:flex-wrap md:justify-center",
    // gap-6 = 1.5rem between cards: two per row leave one gap, three leave two, four leave three.
    card: perRow === 3 ? "md:w-[calc((100%-1.5rem)/2)] lg:w-[calc((100%-3rem)/3)]" : "md:w-[calc((100%-1.5rem)/2)] lg:w-[calc((100%-4.5rem)/4)]",
  };
}

/** The module selector's heading and cards, for exactly the modules this account may open (any number, even none). */
export function ModuleChoice({ modules }: { modules: readonly (Pick<ModuleInfo, "label" | "description" | "href"> & { key: string })[] }) {
  const grid = gridFor(modules.length);
  return (
    <div className={cn("relative z-10 mx-auto w-full max-w-md text-center", grid.width)}>
      <p className="fx-rise mb-3 text-[11px] font-semibold uppercase tracking-[.18em] text-primary sm:hidden">Kiara Intelligence</p>
      <h1 className="fx-rise kiara-gradient-text mb-2 text-balance text-[1.75rem] font-bold leading-[1.05] tracking-tight sm:text-4xl">{!modules.length ? "Boas-vindas à Kiara" : modules.length === 1 ? "Seu módulo de operação" : "Selecione o módulo de operação"}</h1>
      {modules.some(({ key }) => key === "leads")
        ? <p className="fx-rise mb-6 text-sm text-muted-foreground sm:mb-9">Primeira vez aqui? <WelcomeTourLink className="-my-1.5 inline-block py-1.5 text-primary underline-offset-4 hover:underline" /></p>
        : <div className="mb-6 sm:mb-9" />}
      {!modules.length ? (
        <div className="fx-rise mx-auto flex max-w-md flex-col items-center rounded-3xl border border-white/10 bg-black/50 p-8 text-center sm:backdrop-blur-xl">
          <span className="mb-4 rounded-2xl bg-white/5 p-4 text-primary"><LockKeyhole className="size-8" aria-hidden="true" /></span>
          <h2 className="text-lg font-semibold">Nenhum módulo liberado ainda</h2>
          <p className="mt-2 text-sm text-muted-foreground">O administrador da Kiara escolhe os módulos da sua conta. Fale com ele para liberar o acesso.</p>
        </div>
      ) : null}
      <div className={cn("grid-cols-1 gap-3 sm:gap-6", grid.columns)}>
        {modules.map(({ key, href, label, description }, index) => {
          const Icon = ICONS[key] ?? LayoutGrid;
          return (
            <Link key={href} href={href} data-tilt="12" style={{ "--i": index + 1 } as React.CSSProperties} className={cn("fx-rise fx-tilt fx-spot kiara-module-live group relative grid grid-cols-[auto_1fr_auto] items-center gap-x-4 rounded-2xl border border-white/10 bg-black/50 p-4 text-left hover:border-primary/50 hover:bg-black/60 sm:flex sm:flex-col sm:rounded-3xl sm:bg-black/40 sm:p-8 sm:text-center sm:backdrop-blur-xl", grid.card)}>
              <div className="fx-pop kiara-halo-hover row-span-2 rounded-2xl bg-white/5 p-3 text-primary transition-colors group-hover:bg-primary/20 sm:mb-6 sm:p-4">
                <Icon className="size-7 sm:size-10" />
              </div>
              <h2 className="text-base font-semibold sm:mb-2 sm:text-xl">{label}</h2>
              <p className="col-start-2 text-[13px] text-muted-foreground sm:mb-8 sm:text-sm">{description}</p>
              <span className="col-start-3 row-span-2 row-start-1 mt-auto inline-flex size-10 items-center justify-center rounded-full bg-white/5 text-sm font-medium group-hover:bg-primary group-hover:text-primary-foreground sm:min-h-10 sm:w-full sm:rounded-lg sm:bg-transparent">
                <span className="sr-only sm:not-sr-only">Acessar</span> <ArrowRight className="size-4 sm:ml-2" />
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
