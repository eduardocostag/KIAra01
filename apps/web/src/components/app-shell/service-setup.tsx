"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { Check, CircleAlert, FlaskConical, LoaderCircle, Plus, Sparkles, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { EMPTY_SETUP, type Goal, type Niche, type ServiceSetup } from "@/lib/service-setup"

const GOAL_LABELS: Record<Exclude<Goal, "">, { title: string; hint: string }> = {
  schedule: { title: "Agendar", hint: "Avaliação, consulta ou horário" },
  visit: { title: "Marcar visita", hint: "Imóvel, loja ou unidade" },
  quote: { title: "Enviar orçamento", hint: "Proposta com valores" },
  sale: { title: "Vender pelo WhatsApp", hint: "Fechar o pedido na conversa" },
  handoff: { title: "Passar para o vendedor", hint: "A Kiara qualifica e entrega" },
}

/** Configurar atendimento: the client says what the business is, sells and charges, and how Kiara attends.
 *  The niche suggests everything left blank; what the client writes always wins. */
export function ServiceSetupWorkspace({ isAdmin = false, preview }: { isAdmin?: boolean; preview?: { setup: ServiceSetup; niches: Niche[] } }) {
  const [setup, setSetup] = useState<ServiceSetup>({ ...EMPTY_SETUP, ...preview?.setup })
  const [niches, setNiches] = useState<Niche[]>(preview?.niches ?? [])
  const [loading, setLoading] = useState(!preview)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [newTopic, setNewTopic] = useState("")

  useEffect(() => {
    if (preview) return
    const controller = new AbortController()
    fetch("/api/sales/service", { signal: controller.signal }).then(async (response) => {
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível carregar a configuração.")
      setSetup({ ...EMPTY_SETUP, ...body.setup }); setNiches(body.niches ?? [])
    }).catch((reason) => { if (!controller.signal.aborted) setMessage({ ok: false, text: reason instanceof Error ? reason.message : "Não foi possível carregar a configuração." }) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [preview])

  const niche = niches.find((item) => item.id === setup.niche)
  const update = (changes: Partial<ServiceSetup>) => { setSetup((current) => ({ ...current, ...changes })); setDirty(true); setMessage(null) }
  const discover = setup.discover.length ? setup.discover : niche?.discover ?? []
  const goal = setup.goal || niche?.goal || ""

  const priced = setup.services.filter((item) => item.name.trim())
  const checklist = (() => {
    return [
      { done: Boolean(setup.niche && (setup.niche !== "outro" || setup.niche_other.trim())), text: "Nicho escolhido" },
      { done: priced.length > 0, text: "Serviços ou produtos" },
      { done: priced.length > 0 && (setup.hide_prices || priced.every((item) => item.price.trim())), text: "Preços (ou a opção de não informar)" },
      { done: Boolean(setup.hours.trim()), text: "Horário de atendimento" },
      { done: Boolean(goal), text: "Objetivo da conversa" },
    ]
  })()
  const done = checklist.filter((item) => item.done).length

  async function save() {
    setSaving(true); setMessage(null)
    try {
      const response = await fetch("/api/sales/service", { method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...setup, services: setup.services.filter((item) => item.name.trim()) }) })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível salvar.")
      setSetup({ ...EMPTY_SETUP, ...body.setup }); setDirty(false)
      setMessage({ ok: true, text: "Salvo. A Kiara já atende com esta configuração." })
    } catch (reason) {
      setMessage({ ok: false, text: reason instanceof Error ? reason.message : "Não foi possível salvar." })
    } finally { setSaving(false) }
  }

  if (loading) return <div className="grid place-items-center py-24 text-muted-foreground"><LoaderCircle className="size-5 animate-spin" aria-label="Carregando" /></div>

  return <div className="space-y-4 pb-24">
    <div className="flex flex-wrap items-start gap-3">
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-semibold tracking-tight">Configurar atendimento</h1>
        <p className="mt-1 text-sm text-muted-foreground">Conte como é o seu negócio. A Kiara se adapta ao seu nicho e ao seu jeito de atender. Tudo que você deixar em branco vem das boas práticas do nicho.</p>
      </div>
      {isAdmin ? <Button asChild variant="outline" size="sm"><Link href="/app/whatsapp/simulador"><FlaskConical />Testar no Simulador</Link></Button> : null}
    </div>

    <Card className="gap-3 py-4">
      <CardContent className="space-y-2 px-4">
        <div className="flex items-center gap-3"><p className="text-sm font-medium">{done === checklist.length ? "Tudo pronto para atender" : `${done} de ${checklist.length} itens preenchidos`}</p>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden="true"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(done / checklist.length) * 100}%` }} /></div></div>
        <ul className="flex flex-wrap gap-x-4 gap-y-1">{checklist.map((item) => <li key={item.text} className={cn("flex items-center gap-1.5 text-xs", item.done ? "text-muted-foreground" : "text-amber-500")}>
          {item.done ? <Check className="size-3.5 text-emerald-500" aria-hidden="true" /> : <CircleAlert className="size-3.5" aria-hidden="true" />}{item.text}</li>)}</ul>
        {!checklist[2].done && checklist[1].done ? <p className="text-xs text-muted-foreground">Quando perguntarem um preço que não está aqui, a Kiara diz que vai confirmar e avisa você.</p> : null}
      </CardContent>
    </Card>

    <Section title="1. Seu nicho" description="Define como a Kiara conduz a conversa: o que perguntar, onde chegar e o que nunca dizer.">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {[...niches, { id: "outro", label: "Outro" } as Niche].map((item) => <button key={item.id} type="button" aria-pressed={setup.niche === item.id} onClick={() => update({ niche: item.id })}
          className={cn("min-h-11 rounded-xl border px-3 text-left text-sm transition-colors", setup.niche === item.id ? "border-primary bg-primary/10 font-medium" : "hover:bg-muted/50")}>{item.label}</button>)}
      </div>
      {setup.niche === "outro" ? <Input className="mt-3" maxLength={80} value={setup.niche_other} onChange={(event) => update({ niche_other: event.target.value })} placeholder="Qual é o seu ramo? Ex.: pet shop, buffet, energia solar" aria-label="Seu ramo" /> : null}
      {niche ? <p className="mt-3 flex gap-2 rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground"><Sparkles className="size-3.5 shrink-0 text-primary" aria-hidden="true" />{niche.care}</p> : null}
    </Section>

    <Section title="2. Serviços e valores" description="Um por linha. Pode ser valor fechado, faixa (“a partir de”) ou “sob consulta”.">
      <div className="space-y-2">
        {setup.services.map((item, index) => <div key={index} className="flex flex-wrap gap-2 rounded-xl border border-dashed p-2 sm:flex-nowrap sm:border-0 sm:p-0">
          <Input aria-label={`Serviço ${index + 1}`} maxLength={120} value={item.name} placeholder={niche?.examples[index]?.[0] ?? "Serviço ou produto"} className="basis-full sm:basis-auto sm:flex-[2]"
            onChange={(event) => update({ services: setup.services.map((row, at) => at === index ? { ...row, name: event.target.value } : row) })} />
          <Input aria-label={`Valor do serviço ${index + 1}`} maxLength={60} value={item.price} placeholder={setup.hide_prices ? "não aparece" : "Ex.: R$ 150 ou sob consulta"} className="min-w-0 flex-1" disabled={setup.hide_prices}
            onChange={(event) => update({ services: setup.services.map((row, at) => at === index ? { ...row, price: event.target.value } : row) })} />
          <Button type="button" variant="ghost" size="icon" aria-label={`Remover serviço ${index + 1}`} onClick={() => update({ services: setup.services.filter((_, at) => at !== index) })}><X /></Button>
        </div>)}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" disabled={setup.services.length >= 40} onClick={() => update({ services: [...setup.services, { name: "", price: "" }] })}><Plus />Adicionar serviço</Button>
          {!setup.services.length && niche ? <Button type="button" variant="ghost" size="sm" onClick={() => update({ services: niche.examples.map(([name, price]) => ({ name, price })) })}><Sparkles />Começar com exemplos de {niche.label.toLowerCase()}</Button> : null}
        </div>
        <Toggle checked={setup.hide_prices} onChange={(hide_prices) => update({ hide_prices })} label="Não informar preços pelo WhatsApp" hint="A Kiara explica que o valor depende do caso e convida para o próximo passo." />
      </div>
    </Section>

    <Section title="3. Funcionamento">
      <div className="grid gap-3 sm:grid-cols-2">
        <Labeled label="Horário de atendimento"><Input maxLength={300} value={setup.hours} onChange={(event) => update({ hours: event.target.value })} placeholder="Ex.: seg. a sex., 8h às 18h; sáb., 8h às 12h" /></Labeled>
        <Labeled label="Endereço"><Input maxLength={300} value={setup.address} onChange={(event) => update({ address: event.target.value })} placeholder="Ex.: Rua das Flores, 120, Centro, Campinas" /></Labeled>
        <Labeled label={niche?.payment_label ?? "Pagamento e condições"} className="sm:col-span-2"><Input maxLength={500} value={setup.payment} onChange={(event) => update({ payment: event.target.value })} placeholder="Ex.: Pix, cartão em até 6x, convênios aceitos" /></Labeled>
      </div>
    </Section>

    <Section title="4. Objetivo da conversa" description="Aonde a Kiara deve levar o cliente.">
      <div className="grid gap-2 sm:grid-cols-3">{(Object.keys(GOAL_LABELS) as Exclude<Goal, "">[]).map((key) => <button key={key} type="button" aria-pressed={goal === key} onClick={() => update({ goal: key })}
        className={cn("rounded-xl border p-3 text-left transition-colors", goal === key ? "border-primary bg-primary/10" : "hover:bg-muted/50")}>
        <span className="block text-sm font-medium">{GOAL_LABELS[key].title}</span>
        <span className="block text-xs text-muted-foreground">{!setup.goal && niche?.goal === key ? "Sugerido para o seu nicho" : GOAL_LABELS[key].hint}</span>
      </button>)}</div>
      <Labeled label="Detalhe (opcional)" className="mt-3"><Input maxLength={300} value={setup.goal_detail} onChange={(event) => update({ goal_detail: event.target.value })} placeholder="Ex.: agenda online em clinica.com.br/agenda; avaliação dura 30 minutos" /></Labeled>
    </Section>

    <Section title="5. O que descobrir na conversa" description={setup.discover.length || !niche ? "A Kiara pergunta aos poucos, sem questionário." : "Sugestões do seu nicho. Remova ou acrescente o que quiser."}>
      <div className="flex flex-wrap gap-2">{discover.map((item) => <span key={item} className="inline-flex items-center gap-1 rounded-full border bg-muted/30 py-1 pl-3 pr-1 text-sm">{item}
        <button type="button" aria-label={`Remover ${item}`} className="grid size-6 place-items-center rounded-full hover:bg-muted" onClick={() => update({ discover: discover.filter((topic) => topic !== item) })}><X className="size-3.5" /></button></span>)}</div>
      <form className="mt-3 flex gap-2" onSubmit={(event) => { event.preventDefault(); const topic = newTopic.trim(); if (topic && !discover.includes(topic) && discover.length < 12) { update({ discover: [...discover, topic] }); setNewTopic("") } }}>
        <Input maxLength={120} value={newTopic} onChange={(event) => setNewTopic(event.target.value)} placeholder="Ex.: se já é cliente" aria-label="Novo item para descobrir" />
        <Button type="submit" variant="outline" disabled={!newTopic.trim() || discover.length >= 12}><Plus />Adicionar</Button>
      </form>
    </Section>

    <Section title="6. Quando chamar uma pessoa" description={niche && !setup.handoff.trim() ? `Em branco, a Kiara usa o padrão do nicho: ${niche.handoff}` : "A Kiara para e avisa você para continuar a conversa."}>
      <Textarea maxLength={600} value={setup.handoff} onChange={(event) => update({ handoff: event.target.value })} className="min-h-20" placeholder={niche?.handoff ?? "Ex.: pedido de desconto, reclamação, cliente pronto para fechar"} />
    </Section>

    <Section title="7. Tom e limites">
      <div className="grid grid-cols-2 gap-2 sm:max-w-md">{([["friendly", "Descontraído"], ["formal", "Formal"]] as const).map(([key, label]) =>
        <button key={key} type="button" aria-pressed={(setup.tone || "friendly") === key} onClick={() => update({ tone: key })} className={cn("min-h-10 rounded-xl border px-3 text-sm transition-colors", (setup.tone || "friendly") === key ? "border-primary bg-primary/10 font-medium" : "hover:bg-muted/50")}>{label}</button>)}</div>
      <Toggle checked={setup.emojis} onChange={(emojis) => update({ emojis })} label="Pode usar emojis" hint="No máximo um por mensagem, quando combinar." />
      <Labeled label="O que a Kiara nunca deve dizer ou prometer" className="mt-3"><Textarea maxLength={600} value={setup.never_say} onChange={(event) => update({ never_say: event.target.value })} className="min-h-20" placeholder="Ex.: não dar desconto; não falar de concorrentes; não prometer prazo de entrega" /></Labeled>
    </Section>

    <Section title="8. Outras informações" description="Diferenciais, políticas, perguntas frequentes, qualquer coisa que ajude a responder.">
      <Textarea maxLength={4000} value={setup.extra} onChange={(event) => update({ extra: event.target.value })} className="min-h-28" placeholder="Ex.: estacionamento próprio; atendemos crianças a partir de 3 anos; garantia de 1 ano" />
    </Section>

    <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center gap-3 border-t bg-background/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
      <p role="status" className={cn("min-w-0 flex-1 text-sm", message ? (message.ok ? "text-emerald-500" : "text-destructive") : "text-muted-foreground")}>{message?.text ?? (dirty ? "Alterações não salvas" : "Tudo salvo")}</p>
      <Button type="button" onClick={() => void save()} disabled={saving || !dirty}>{saving ? <LoaderCircle className="animate-spin" /> : <Check />}Salvar</Button>
    </div>
  </div>
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return <Card className="gap-4 py-5"><CardHeader className="px-4 sm:px-5"><CardTitle className="text-base">{title}</CardTitle>{description ? <CardDescription>{description}</CardDescription> : null}</CardHeader><CardContent className="px-4 sm:px-5">{children}</CardContent></Card>
}

function Labeled({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return <label className={cn("block space-y-1.5", className)}><span className="text-sm font-medium">{label}</span>{children}</label>
}

function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (value: boolean) => void; label: string; hint: string }) {
  return <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="mt-3 flex w-full items-center gap-3 rounded-xl border p-3 text-left hover:bg-muted/40">
    <span className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors", checked ? "bg-primary" : "bg-muted-foreground/30")}><span className={cn("absolute top-0.5 size-4 rounded-full bg-white transition-all", checked ? "left-[18px]" : "left-0.5")} /></span>
    <span><span className="block text-sm font-medium">{label}</span><span className="block text-xs text-muted-foreground">{hint}</span></span>
  </button>
}
