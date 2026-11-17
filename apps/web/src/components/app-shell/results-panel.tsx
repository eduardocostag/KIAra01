"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { salesRequest, type SalesProfile } from "@/lib/api/sales"
import { cn } from "@/lib/utils"

type Metrics = { found: number; added: number; approached: number; conversations: number; replied: number; opportunities: number; won: number; generated_cents: number; won_cents: number }
type Results = { days: number; current: Metrics; previous: Metrics; open_cents: number; average_deal_cents: number }

const PERIODS = [{ days: 7, label: "7 dias" }, { days: 30, label: "30 dias" }, { days: 90, label: "90 dias" }]
const money = (cents: number, compact = false) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: compact || cents >= 1_000_000 ? 0 : 2, ...(compact && cents >= 100_000_000 ? { notation: "compact" } : {}) }).format(cents / 100)
const number = (value: number) => new Intl.NumberFormat("pt-BR").format(value)

function Trend({ now, before }: { now: number; before: number }) {
  if (!before && !now) return null
  if (!before) return <span className="rounded-full bg-emerald-400/10 px-1.5 py-0.5 text-[11px] text-emerald-300">novo</span>
  const change = Math.round(((now - before) / before) * 100)
  if (!change) return null
  const Icon = change > 0 ? ArrowUpRight : ArrowDownRight
  return <span className={cn("inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] tabular-nums", change > 0 ? "bg-emerald-400/10 text-emerald-300" : "bg-rose-400/10 text-rose-300")}><Icon className="size-3.5" aria-hidden="true" />{change > 0 ? "+" : ""}{change}%<span className="sr-only"> em relação ao período anterior</span></span>
}

/** What Kiara produced in the period: one headline in money, the funnel of the period and a few tiles. */
export function ResultsPanel() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<Results | null>(null)
  const [error, setError] = useState("")
  const [average, setAverage] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (period: number) => {
    setError("")
    try { setData(await salesRequest<Results>(`/api/sales/results?days=${period}`)) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar os resultados.") }
  }, [])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(days) }, [days, load])

  async function saveAverage() {
    const cents = Math.round(Number(average.replace(/\./g, "").replace(",", ".")) * 100)
    if (!Number.isFinite(cents) || cents <= 0) { setError("Informe um valor em reais, por exemplo 1.500."); return }
    setSaving(true); setError("")
    try {
      const profile = await salesRequest<SalesProfile>("/api/sales/profile")
      const body: Partial<SalesProfile> = { ...profile, average_deal_cents: cents }
      delete body.updated_at  // read-only: the API refuses unknown fields
      await salesRequest("/api/sales/profile", { method: "PUT", body: JSON.stringify(body) })
      await load(days)
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível salvar.") }
    finally { setSaving(false) }
  }

  const current = data?.current
  const steps = current ? [
    { label: "Encontrados", value: current.found },
    { label: "Abordados", value: current.approached },
    { label: "Responderam", value: current.replied },
    { label: "Oportunidades", value: current.opportunities },
    { label: "Vendas", value: current.won },
  ] : []
  const top = Math.max(1, ...steps.map((step) => step.value))
  const empty = Boolean(current && !steps.some((step) => step.value) && !current.generated_cents && !data?.open_cents && !current.conversations)
  const noMoney = data && !empty && !data.average_deal_cents && !data.current.generated_cents && !data.current.won_cents
  const replyRate = current?.approached ? Math.round((current.replied / current.approached) * 100) : 0

  return <section aria-labelledby="results-title" className="kiara-results kiara-soft-panel rounded-2xl border p-5 sm:p-7">
    <header className="flex items-center gap-3">
      <h2 id="results-title" className="flex-1 text-[13px] font-medium uppercase tracking-[.14em] text-muted-foreground">Resultados</h2>
      <div role="radiogroup" aria-label="Período" className="flex items-center gap-1 text-xs">{PERIODS.map((period) => <button key={period.days} type="button" role="radio" aria-checked={days === period.days} onClick={() => setDays(period.days)}
        className={cn("rounded-full px-2.5 py-1 transition-colors", days === period.days ? "bg-white/[.08] text-foreground" : "text-muted-foreground hover:text-foreground")}>{period.label.replace(" dias", "d")}</button>)}</div>
    </header>

    {error ? <p role="alert" className="mt-4 text-sm text-destructive">{error}</p> : null}
    {!data && !error ? <div role="status" aria-label="Carregando resultados" className="mt-6 space-y-4"><div className="fx-skeleton h-12 w-48 rounded-lg" /><div className="fx-skeleton h-16 rounded-xl" /></div> : null}

    {data && current && empty ? <div className="mt-6 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
      <div className="flex-1">
        <p className="text-2xl font-semibold tracking-tight">Nada por aqui ainda</p>
        <p className="mt-1 text-sm text-muted-foreground">Nos últimos {data.days} dias não houve buscas nem conversas. Quando a Kiara trabalhar, os resultados aparecem aqui.</p>
      </div>
      <Button asChild variant="outline" className="rounded-full"><Link href="/app/hunter">Buscar leads<ArrowRight /></Link></Button>
    </div> : null}

    {data && current && !empty ? <>
      <div className="mt-5 flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <p className="text-[44px] font-semibold leading-none tracking-[-.04em] tabular-nums sm:text-5xl">{money(current.generated_cents, true)}</p>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">em oportunidades geradas <Trend now={current.generated_cents} before={data.previous.generated_cents} /></p>
        </div>
        <dl className="flex gap-8 pb-1 text-sm">
          <div><dt className="text-muted-foreground">Vendas</dt><dd className="mt-0.5 text-lg font-medium tabular-nums">{money(current.won_cents, true)}</dd></div>
          <div><dt className="text-muted-foreground">Em negociação</dt><dd className="mt-0.5 text-lg font-medium tabular-nums">{money(data.open_cents, true)}</dd></div>
        </dl>
      </div>

      {noMoney ? <form className="mt-5 flex flex-wrap items-center gap-2 rounded-xl bg-white/[.03] p-3 text-sm" onSubmit={(event) => { event.preventDefault(); void saveAverage() }}>
        <label htmlFor="average-deal" className="flex-1 text-muted-foreground">Quanto vale, em média, uma venda sua? Assim a Kiara mostra o resultado em reais.</label>
        <span className="flex items-center rounded-md border bg-background px-2"><span className="text-muted-foreground">R$</span><input id="average-deal" inputMode="decimal" value={average} onChange={(event) => setAverage(event.target.value)} placeholder="1.500" className="h-9 w-28 bg-transparent px-2 outline-none" /></span>
        <Button type="submit" size="sm" disabled={saving}>Salvar</Button>
      </form> : null}

      <ol className="mt-7 grid grid-cols-3 gap-x-4 gap-y-5 border-t border-white/[.06] pt-6 sm:grid-cols-5 sm:gap-0" aria-label={`Funil dos últimos ${data.days} dias`}>{steps.map((step, index) => {
        const previous = index ? steps[index - 1].value : 0
        const rate = index && previous ? Math.round((step.value / previous) * 100) : null
        return <li key={step.label} className="relative min-w-0 sm:px-4 sm:first:pl-0 sm:[&:not(:first-child)]:border-l sm:[&:not(:first-child)]:border-white/[.06]" title={rate !== null ? `${rate}% da etapa anterior` : undefined}>
          <p className="truncate text-xs text-muted-foreground">{step.label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{number(step.value)}</p>
          <span className="mt-2 block h-[3px] overflow-hidden rounded-full bg-white/[.06]"><span className="block h-full rounded-full bg-gradient-to-r from-violet-400 to-sky-400 transition-[width] duration-700" style={{ width: `${(step.value / top) * 100}%` }} /></span>
          {rate !== null ? <p className="mt-1.5 text-[11px] tabular-nums text-muted-foreground">{rate}%<span className="hidden sm:inline"> da etapa anterior</span></p> : <p className="mt-1.5 text-[11px] text-transparent" aria-hidden="true">.</p>}
        </li>
      })}</ol>

      <p className="mt-6 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
        <span><span className="font-medium text-foreground tabular-nums">{number(current.conversations)}</span> conversas no WhatsApp</span>
        <span><span className="font-medium text-foreground tabular-nums">{number(current.added)}</span> leads no funil</span>
        <span><span className="font-medium text-foreground tabular-nums">{replyRate}%</span> de resposta</span>
      </p>
    </> : null}
  </section>
}
