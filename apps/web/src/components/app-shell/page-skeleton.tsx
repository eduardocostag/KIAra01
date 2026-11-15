/** Placeholder shaped like the page that is loading, so the screen never goes blank or jumps. */
const bar = "fx-skeleton rounded-md"

function Header() {
  return <div className="space-y-2"><div className={`${bar} h-8 w-56`} /><div className={`${bar} h-4 w-80 max-w-full`} /></div>
}

export function PageSkeleton({ variant = "list" }: { variant?: "list" | "board" | "detail" | "inbox" | "cards" }) {
  return <div role="status" aria-live="polite" aria-label="Carregando" className="mx-auto w-full max-w-6xl space-y-6">
    <span className="sr-only">Carregando…</span>
    <Header />
    {variant === "board" ? <div className="grid gap-4 overflow-hidden sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((column) => <div key={column} className="space-y-3 rounded-xl border bg-card p-3">
      <div className={`${bar} h-5 w-28`} />{Array.from({ length: 3 - (column % 2) }, (_, card) => <div key={card} className="space-y-2 rounded-lg border p-3"><div className={`${bar} h-4 w-3/4`} /><div className={`${bar} h-3 w-1/2`} /></div>)}
    </div>)}</div>
      : variant === "detail" ? <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4 rounded-xl border bg-card p-5">{[0, 1, 2, 3, 4].map((line) => <div key={line} className={`${bar} h-4`} style={{ width: `${90 - line * 12}%` }} />)}</div>
        <div className="space-y-3 rounded-xl border bg-card p-5"><div className={`${bar} h-5 w-32`} />{[0, 1, 2].map((line) => <div key={line} className={`${bar} h-9 w-full`} />)}</div>
      </div>
      : variant === "inbox" ? <div className="grid min-h-[60vh] gap-4 md:grid-cols-[320px_1fr]">
        <div className="space-y-2 rounded-xl border bg-card p-3">{[0, 1, 2, 3, 4, 5].map((row) => <div key={row} className="flex items-center gap-3 p-2"><div className="fx-skeleton size-9 shrink-0 rounded-full" /><div className="flex-1 space-y-1.5"><div className={`${bar} h-3.5 w-2/3`} /><div className={`${bar} h-3 w-1/2`} /></div></div>)}</div>
        <div className="hidden space-y-4 rounded-xl border bg-card p-5 md:block">{[0, 1, 2].map((row) => <div key={row} className={`${bar} h-12`} style={{ width: row % 2 ? "45%" : "60%", marginLeft: row % 2 ? "auto" : 0 }} />)}</div>
      </div>
      : variant === "cards" ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((card) => <div key={card} className="space-y-3 rounded-xl border bg-card p-5"><div className={`${bar} h-5 w-1/2`} /><div className={`${bar} h-3 w-full`} /><div className={`${bar} h-3 w-4/5`} /></div>)}</div>
      : <div className="overflow-hidden rounded-xl border bg-card">
        <div className="border-b p-4"><div className={`${bar} h-9 w-full max-w-md`} /></div>
        {[0, 1, 2, 3, 4, 5].map((row) => <div key={row} className="flex items-center gap-4 border-b p-4 last:border-0"><div className="fx-skeleton size-11 shrink-0 rounded-full" /><div className="flex-1 space-y-2"><div className={`${bar} h-4 w-1/3`} /><div className={`${bar} h-3 w-2/3`} /></div><div className={`${bar} hidden h-8 w-24 sm:block`} /></div>)}
      </div>}
  </div>
}
