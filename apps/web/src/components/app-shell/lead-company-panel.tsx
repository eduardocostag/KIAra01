"use client"

import { useState } from "react"
import { Building2, CircleAlert, Gauge, LoaderCircle, RefreshCw, Search, Trash2, TrendingDown, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { parseCompany, parseLeadFit, type CompanyData, type LeadFit } from "@/lib/api/pipeline"
import { cn } from "@/lib/utils"

const gradeStyles: Record<LeadFit["grade"], string> = {
  A: "from-emerald-400 to-teal-300 text-emerald-950",
  B: "from-sky-400 to-indigo-300 text-sky-950",
  C: "from-amber-300 to-orange-300 text-amber-950",
  D: "from-zinc-400 to-zinc-500 text-zinc-950",
}
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })

const sizeLabels: Record<string, string> = { "MICRO EMPRESA": "Microempresa", "EMPRESA DE PEQUENO PORTE": "Pequeno porte", DEMAIS: "Médio ou grande porte" }

function formatDate(value: string | null) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split("-")
  return `${day}/${month}/${year}`
}

function maskCnpj(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 14)
  return digits.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2")
}

export function LeadCompanyPanel({ leadId, initialCompany, initialFit }: { leadId: string; initialCompany: CompanyData | null; initialFit: LeadFit | null }) {
  const [company, setCompany] = useState(initialCompany)
  const [fit, setFit] = useState(initialFit)
  const [cnpj, setCnpj] = useState("")
  const [manual, setManual] = useState(false)
  const [busy, setBusy] = useState<"" | "lookup" | "remove">("")
  const [error, setError] = useState("")

  async function send(method: "POST" | "DELETE", body?: unknown) {
    setBusy(method === "POST" ? "lookup" : "remove"); setError("")
    try {
      const response = await fetch(`/api/leads/${encodeURIComponent(leadId)}/company`, {
        method, cache: "no-store", headers: { "Content-Type": "application/json" }, ...(body ? { body: JSON.stringify(body) } : {}),
      })
      const payload: unknown = await response.json().catch(() => null)
      if (!response.ok) {
        const message = (payload as { error?: { message?: unknown } } | null)?.error?.message
        const code = (payload as { error?: { code?: unknown } } | null)?.error?.code
        if (code === "cnpj_required" || code === "cnpj_not_on_website") setManual(true)
        throw new Error(typeof message === "string" ? message : `A consulta não foi concluída (HTTP ${response.status}).`)
      }
      const data = payload as { company?: unknown; fit?: unknown }
      setCompany(parseCompany(data.company)); setFit(parseLeadFit(data.fit)); setCnpj(""); setManual(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "A consulta não foi concluída.")
    } finally { setBusy("") }
  }

  const facts = company ? [
    { label: "CNPJ", value: company.cnpj_formatted },
    { label: "Situação", value: company.status },
    { label: "Abertura", value: formatDate(company.opened_at) },
    { label: "Porte", value: company.mei ? "MEI" : company.size ? sizeLabels[company.size.toUpperCase()] ?? company.size : null },
    { label: "Atividade principal", value: company.main_activity },
    { label: "Cidade", value: [company.city, company.state].filter(Boolean).join(" / ") || null },
    { label: "Capital social", value: company.capital ? brl.format(company.capital) : null },
    { label: "Natureza jurídica", value: company.legal_nature },
  ].filter((item) => item.value) : []

  return <section className="kiara-lead-panel kiara-lead-company" aria-labelledby="lead-company-title">
    <div className="flex flex-wrap items-start gap-4">
      {fit ? <div className="flex items-center gap-3" aria-label={`Nota do lead: ${fit.score} de 100, ${fit.label}`}>
        <span className={cn("grid size-16 shrink-0 place-items-center rounded-2xl bg-gradient-to-br text-2xl font-bold shadow-lg", gradeStyles[fit.grade])}>{fit.grade}</span>
        <div>
          <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground"><Gauge className="size-3.5" aria-hidden="true" />Nota do lead</p>
          <p className="text-2xl font-semibold tabular-nums">{fit.score}<span className="text-sm font-normal text-muted-foreground">/100</span></p>
          <p className="text-sm text-muted-foreground">{fit.label}</p>
        </div>
      </div> : null}
      <div className="min-w-0 flex-1 basis-64">
        <h2 id="lead-company-title" className="flex items-center gap-2"><Building2 className="size-4" aria-hidden="true" />Por que essa nota</h2>
        {fit?.reasons.length ? <ul className="mt-2 space-y-1.5 text-sm">{fit.reasons.map((reason) => <li key={reason.text} className="flex items-start gap-2">
          {reason.points >= 0 ? <TrendingUp className="mt-0.5 size-4 shrink-0 text-emerald-400" aria-hidden="true" /> : <TrendingDown className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />}
          <span>{reason.text} <span className="text-xs text-muted-foreground tabular-nums">({reason.points > 0 ? "+" : ""}{reason.points})</span></span>
        </li>)}</ul> : <p className="mt-2 text-sm text-muted-foreground">Ainda há poucos dados sobre este lead. Busque o CNPJ para uma nota mais precisa.</p>}
      </div>
    </div>

    <div className="mt-5 border-t pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto font-semibold">Dados da Receita Federal</h3>
        {company ? <>
          <Button type="button" size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => void send("POST", { cnpj: company.cnpj })}>{busy === "lookup" ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}Atualizar</Button>
          <Button type="button" size="sm" variant="ghost" className="text-muted-foreground" disabled={Boolean(busy)} onClick={() => void send("DELETE")} title="Use se o CNPJ não for desta empresa">{busy === "remove" ? <LoaderCircle className="animate-spin" /> : <Trash2 />}Não é esta empresa</Button>
        </> : <Button type="button" size="sm" disabled={Boolean(busy)} onClick={() => void send("POST", {})}>{busy === "lookup" ? <LoaderCircle className="animate-spin" /> : <Search />}{busy === "lookup" ? "Procurando no site…" : "Buscar CNPJ no site"}</Button>}
      </div>

      {company ? <>
        <p className="mt-2 text-sm"><strong>{company.trade_name || company.legal_name}</strong>{company.trade_name && company.legal_name ? <span className="text-muted-foreground"> · {company.legal_name}</span> : null}</p>
        {!company.active ? <p className="mt-2 flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive"><CircleAlert className="size-4" />Situação cadastral: {company.status ?? "irregular"}. Confirme antes de abordar.</p> : null}
        <dl className="kiara-lead-facts mt-3">{facts.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
        {company.partners?.length ? <p className="mt-3 text-sm"><span className="text-muted-foreground">Sócios: </span>{company.partners.map((partner) => [partner.name, partner.role && `(${partner.role})`].filter(Boolean).join(" ")).join(" · ")}</p> : null}
        <p className="mt-3 text-xs text-muted-foreground">Fonte: Receita Federal via {company.source === "brasilapi" ? "BrasilAPI" : "Minha Receita"} · CNPJ {company.cnpj_source === "website" ? "encontrado no site da empresa" : "informado manualmente"}.</p>
      </> : <p className="mt-2 text-sm text-muted-foreground">A Kiara procura o CNPJ no rodapé do site da empresa e consulta a Receita Federal: razão social, situação, data de abertura, porte, atividade e sócios.</p>}

      {!company && (manual || error) ? <form className="mt-3 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); void send("POST", { cnpj }) }}>
        <label htmlFor={`cnpj-${leadId}`} className="sr-only">CNPJ</label>
        <Input id={`cnpj-${leadId}`} inputMode="numeric" autoComplete="off" placeholder="00.000.000/0000-00" value={cnpj} onChange={(event) => setCnpj(maskCnpj(event.target.value))} className="h-9 w-56" />
        <Button type="submit" size="sm" variant="outline" disabled={Boolean(busy) || cnpj.replace(/\D/g, "").length !== 14}>Consultar</Button>
      </form> : null}
      {error ? <p role="alert" className="mt-2 text-sm text-destructive">{error}</p> : null}
    </div>
  </section>
}
