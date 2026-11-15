"use client"

import { useCallback, useEffect, useState } from "react"
import { ArrowDownRight, ArrowUpRight, CircleDollarSign, Handshake, MessageCircle, Reply, Search, Send, Trophy } from "lucide-react"
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
  if (!before) return <span className="text-xs text-emerald-400">novo</span>
  const change = Math.round(((now - before) / before) * 100)
  if (!change) return <span className="text-xs text-muted-foreground">igual ao período anterior</span>
  const Icon = change > 0 ? ArrowUpRight : ArrowDownRight
  return <span className={cn("inline-flex items-center gap-0.5 text-xs", change > 0 ? "text-emerald-400" : "text-rose-400")}><Icon className="size-3.5" aria-hidden="true" />{change > 0 ? "+" : ""}{change}%<span className="sr-only"> em relação ao período anterior</span></span>
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
    { label: "Leads encontrados", value: current.found, icon: Search },
    { label: "Abordados", value: current.approached, icon: Send },
    { label: "Responderam", value: current.replied, icon: Reply },
    { label: "Oportunidades", value: current.opportunities, icon: Handshake },
    { label: "Vendas", value: current.won, icon: Trophy },
  ] : []
  const top = Math.max(1, ...steps.map((step) => step.value))
  const noMoney = data && !data.average_deal_cents && !data.current.generated_cents && !data.current.won_cents

  return <section aria-labelledby="results-title" className="kiara-soft-panel space-y-5 rounded-2xl border p-5 sm:p-6">
    <div className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1"><h2 id="results-title" className="text-lg font-semibold">Resultados da Kiara</h2><p className="text-sm text-muted-foreground">O que a Kiara gerou para o seu negócio no período.</p></div>
      <div role="radiogroup" aria-label="Período" className="inline-flex rounded-full border p-0.5">{PERIODS.map((period) => <button key={period.days} type="button" role="radio" aria-checked={days === period.days} onClick={() => setDays(period.days)} className={cn("rounded-full px-3 py-1 text-xs transition-colors", days === period.days ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>{period.label}</button>)}</div>
    </div>

    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {!data && !error ? <div role="status" aria-label="Carregando resultados" className="grid gap-3 sm:grid-cols-3">{[0, 1, 2].map((item) => <div key={item} className="fx-skeleton h-20 rounded-xl" />)}</div> : null}

    {data && current ? <>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground"><CircleDollarSign className="size-4 text-primary" aria-hidden="true" />Oportunidades geradas</p>
          <p className="mt-1 text-4xl font-semibold tracking-tight tabular-nums">{money(current.generated_cents, true)}</p>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground"><Trend now={current.generated_cents} before={data.previous.generated_cents} /></p>
        </div>
        <div className="pb-1">
          <p className="text-sm text-muted-foreground">Vendas fechadas</p>
          <p className="text-2xl font-semibold tabular-nums">{money(current.won_cents, true)}</p>
        </div>
        <div className="pb-1">
          <p className="text-sm text-muted-foreground">Em negociação agora</p>
          <p className="text-2xl font-semibold tabular-nums">{money(data.open_cents, true)}</p>
        </div>
      </div>
      {noMoney ? <form className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed p-3 text-sm" onSubmit={(event) => { event.preventDefault(); void saveAverage() }}>
        <label htmlFor="average-deal" className="flex-1 text-muted-foreground">Quanto vale, em média, uma venda sua? Assim a Kiara mostra o resultado em reais.</label>
        <span className="flex items-center rounded-md border bg-background px-2"><span className="text-muted-foreground">R$</span><input id="average-deal" inputMode="decimal" value={average} onChange={(event) => setAverage(event.target.value)} placeholder="1.500" className="h-9 w-28 bg-transparent px-2 outline-none" /></span>
        <Button type="submit" size="sm" disabled={saving}>Salvar</Button>
      </form> : null}

      <ol className="space-y-2" aria-label={`Funil dos últimos ${data.days} dias`}>{steps.map((step, index) => {
        const previous = index ? steps[index - 1].value : 0
        const rate = index && previous ? Math.round((step.value / previous) * 100) : null
        const Icon = step.icon
        return <li key={step.label} className="group grid grid-cols-[minmax(0,9.5rem)_1fr_auto] items-center gap-3 text-sm" title={`${step.label}: ${number(step.value)}${rate !== null ? ` (${rate}% da etapa anterior)` : ""}`}>
          <span className="flex items-center gap-2 truncate text-muted-foreground"><Icon className="size-4 shrink-0" aria-hidden="true" />{step.label}</span>
          <span className="h-6 overflow-hidden rounded-md bg-muted/40"><span className="block h-full rounded-r-[4px] bg-primary/80 transition-[width,background-color] duration-700 group-hover:bg-primary" style={{ width: `${Math.max(step.value ? 2 : 0, (step.value / top) * 100)}%` }} /></span>
          <span className="w-24 text-right tabular-nums"><span className="font-semibold">{number(step.value)}</span>{rate !== null ? <span className="ml-1.5 text-xs text-muted-foreground">{rate}%</span> : null}</span>
        </li>
      })}</ol>

      <div className="grid gap-3 sm:grid-cols-3">
        {[{ label: "Conversas no WhatsApp", value: current.conversations, before: data.previous.conversations, icon: MessageCircle },
          { label: "Leads no funil", value: current.added, before: data.previous.added, icon: Handshake },
          { label: "Taxa de resposta", value: current.approached ? Math.round((current.replied / current.approached) * 100) : 0, before: data.previous.approached ? Math.round((data.previous.replied / data.previous.approached) * 100) : 0, icon: Reply, percent: true }]
          .map(({ label, value, before, icon: Icon, percent }) => <div key={label} className="rounded-xl border bg-card/60 p-3">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><Icon className="size-3.5" aria-hidden="true" />{label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{percent ? `${value}%` : number(value)}</p>
            <Trend now={value} before={before} />
          </div>)}
      </div>
    </> : null}
  </section>
}
