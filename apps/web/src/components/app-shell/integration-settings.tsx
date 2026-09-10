"use client"

import { useEffect, useState } from "react"
import { ArrowRight, BarChart3, CheckCircle2, ExternalLink, KeyRound, Loader2, MessageCircle, ShieldCheck, X } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

type Provider = "google" | "instagram"
type Status = { provider: Provider; configured_fields: string[]; status: string; updated_at: string }
type Field = { name: string; label: string; secret?: boolean; required?: boolean; placeholder?: string }
const fields: Record<Provider, Field[]> = {
  google: [{ name: "developer_token", label: "Developer token", secret: true, required: true }, { name: "client_id", label: "OAuth Client ID", required: true, placeholder: "...apps.googleusercontent.com" }, { name: "client_secret", label: "OAuth Client Secret", secret: true, required: true }, { name: "refresh_token", label: "Refresh token", secret: true, required: true }, { name: "customer_id", label: "ID da conta cliente", required: true, placeholder: "10 dígitos, sem hífens" }, { name: "login_customer_id", label: "ID da conta gerente" }, { name: "ga4_property_id", label: "ID da propriedade GA4" }],
  instagram: [{ name: "app_id", label: "Meta App ID", required: true }, { name: "app_secret", label: "Meta App Secret", secret: true, required: true }, { name: "access_token", label: "Access token de longa duração", secret: true, required: true }, { name: "instagram_account_id", label: "Instagram Business Account ID", required: true }, { name: "page_id", label: "Facebook Page ID" }, { name: "verify_token", label: "Webhook verify token", secret: true }],
}
const info = {
  google: { name: "Google Growth", detail: "Ads, Analytics e Data Manager", href: "https://ads.google.com/aw/apicenter", icon: BarChart3 },
  instagram: { name: "Instagram", detail: "Mensagens e conta profissional", href: "https://developers.facebook.com/apps/", icon: MessageCircle },
}

export function IntegrationSettings() {
  const [statuses, setStatuses] = useState<Status[]>([]), [selected, setSelected] = useState<Provider | null>(null)
  const [saving, setSaving] = useState<Provider | null>(null), [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null)
  useEffect(() => { fetch("/api/integrations", { cache: "no-store" }).then(async (response) => response.ok ? setStatuses((await response.json()).items ?? []) : undefined).catch(() => undefined) }, [])
  async function save(provider: Provider, form: HTMLFormElement) {
    setSaving(provider); setMessage(null)
    const credentials = Object.fromEntries(Array.from(new FormData(form).entries()).map(([key, value]) => [key, String(value)]).filter(([, value]) => value.trim()))
    try { const response = await fetch(`/api/integrations/${provider}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credentials }) }); const body = await response.json(); if (!response.ok) throw new Error(body?.error?.message ?? "Não foi possível salvar a integração."); setStatuses((current) => [...current.filter((item) => item.provider !== provider), body]); form.reset(); setMessage({ type: "ok", text: "Credenciais criptografadas e salvas para este workspace." }) }
    catch (error) { setMessage({ type: "error", text: error instanceof Error ? error.message : "Falha ao salvar." }) }
    finally { setSaving(null) }
  }
  return <section className="space-y-5">
    <div className="grid gap-4 md:grid-cols-2">{(["google", "instagram"] as Provider[]).map((provider) => { const providerInfo = info[provider], Icon = providerInfo.icon, status = statuses.find((item) => item.provider === provider); return <button key={provider} type="button" onClick={() => setSelected(provider)} className={cn("group relative overflow-hidden rounded-[28px] border bg-card p-6 text-left shadow-[var(--shadow-1)] transition duration-200 hover:-translate-y-1 hover:border-primary/25 hover:shadow-[var(--shadow-2)]", selected === provider && "border-primary/30 ring-4 ring-primary/5")}><div className="absolute -right-10 -top-10 size-36 rounded-full bg-primary/8 blur-3xl" /><div className="relative flex items-start justify-between"><span className="grid size-12 place-items-center rounded-2xl bg-primary/10 text-primary"><Icon className="size-5" /></span><Badge variant={status ? "secondary" : "outline"} className="rounded-full">{status ? "Configurado" : "Não conectado"}</Badge></div><h2 className="kiara-editorial relative mt-8 text-2xl">{providerInfo.name}</h2><p className="relative mt-2 text-sm text-muted-foreground">{providerInfo.detail}</p><span className="relative mt-7 flex items-center gap-2 text-xs font-semibold text-primary">{status ? "Revisar conexão" : "Configurar conexão"}<ArrowRight className="size-3.5 transition group-hover:translate-x-1" /></span></button> })}</div>
    {!selected ? <div className="kiara-copilot-stage kiara-soft-panel flex min-h-60 flex-col items-center justify-center p-8 text-center"><KiaraOrb size="md" active /><h2 className="kiara-editorial mt-6 text-2xl">Escolha uma conexão para começar.</h2><p className="mt-2 max-w-lg text-sm text-muted-foreground">A Kiara mostra somente os dados necessários e mantém cada segredo isolado por workspace.</p></div> : <div className="overflow-hidden rounded-[28px] border bg-card shadow-[var(--shadow-2)]"><header className="flex items-center justify-between border-b p-6"><div><p className="text-xs font-semibold text-primary">Configuração protegida</p><h2 className="kiara-editorial mt-1 text-2xl">Conectar {info[selected].name}</h2></div><Button size="icon" variant="ghost" onClick={() => setSelected(null)} aria-label="Fechar configuração"><X /></Button></header><div className="p-6 sm:p-8">{message && <Alert variant={message.type === "error" ? "destructive" : "default"} className="mb-6"><ShieldCheck /><AlertTitle>{message.type === "ok" ? "Tudo certo" : "Revise os dados"}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert>}<form onSubmit={(event) => { event.preventDefault(); void save(selected, event.currentTarget) }} autoComplete="off"><div className="grid gap-5 md:grid-cols-2">{fields[selected].map((field) => <div className="grid gap-2" key={field.name}><Label htmlFor={`${selected}-${field.name}`}>{field.label}{field.required ? <span className="text-primary"> *</span> : <span className="font-normal text-muted-foreground"> · opcional</span>}</Label><div className="relative"><Input className="h-12 rounded-xl bg-background pr-10" id={`${selected}-${field.name}`} name={field.name} type={field.secret ? "password" : "text"} required={field.required} placeholder={statuses.find((item) => item.provider === selected)?.configured_fields.includes(field.name) ? "Já configurado — digite para substituir" : field.placeholder} autoComplete="new-password" />{field.secret && <KeyRound className="absolute right-3 top-4 size-4 text-muted-foreground" />}</div></div>)}</div><div className="mt-8 flex flex-col-reverse gap-3 border-t pt-6 sm:flex-row sm:justify-between"><Button asChild variant="outline"><a href={info[selected].href} target="_blank" rel="noreferrer">Gerar credenciais oficiais<ExternalLink /></a></Button><Button type="submit" size="lg" disabled={saving !== null}>{saving ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}Salvar conexão</Button></div></form></div></div>}
  </section>
}
