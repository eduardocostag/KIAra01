"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, ExternalLink, KeyRound, Loader2, ShieldCheck } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type Provider = "google" | "instagram"
type Status = { provider: Provider; configured_fields: string[]; status: string; updated_at: string }
type Field = { name: string; label: string; secret?: boolean; required?: boolean; placeholder?: string }

const fields: Record<Provider, Field[]> = {
  google: [
    { name: "developer_token", label: "Developer token", secret: true, required: true },
    { name: "client_id", label: "OAuth Client ID", required: true, placeholder: "...apps.googleusercontent.com" },
    { name: "client_secret", label: "OAuth Client Secret", secret: true, required: true },
    { name: "refresh_token", label: "Refresh token", secret: true, required: true },
    { name: "customer_id", label: "ID da conta cliente", required: true, placeholder: "10 dígitos, sem hífens" },
    { name: "login_customer_id", label: "ID da conta gerente", placeholder: "Necessário para contas gerenciadas" },
    { name: "ga4_property_id", label: "ID da propriedade GA4", placeholder: "Somente números" },
  ],
  instagram: [
    { name: "app_id", label: "Meta App ID", required: true },
    { name: "app_secret", label: "Meta App Secret", secret: true, required: true },
    { name: "access_token", label: "Access token de longa duração", secret: true, required: true },
    { name: "instagram_account_id", label: "Instagram Business Account ID", required: true },
    { name: "page_id", label: "Facebook Page ID" },
    { name: "verify_token", label: "Webhook verify token", secret: true },
  ],
}

const help: Record<Provider, { title: string; href: string; text: string }> = {
  google: { title: "Abrir central da API Google Ads", href: "https://ads.google.com/aw/apicenter", text: "Crie um projeto no Google Cloud, habilite Google Ads, Analytics Admin/Data e Data Manager e gere OAuth. Tokens pendentes funcionam apenas em contas de teste." },
  instagram: { title: "Abrir Meta for Developers", href: "https://developers.facebook.com/apps/", text: "Crie um app Business, adicione Instagram API/Messaging e use uma conta profissional vinculada a uma Página do Facebook." },
}

export function IntegrationSettings() {
  const [statuses, setStatuses] = useState<Status[]>([])
  const [saving, setSaving] = useState<Provider | null>(null)
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null)

  useEffect(() => { fetch("/api/integrations", { cache: "no-store" }).then(async response => response.ok ? setStatuses((await response.json()).items ?? []) : undefined).catch(() => undefined) }, [])

  async function save(provider: Provider, form: HTMLFormElement) {
    setSaving(provider); setMessage(null)
    const credentials = Object.fromEntries(Array.from(new FormData(form).entries()).map(([key, value]) => [key, String(value)]).filter(([, value]) => value.trim()))
    try {
      const response = await fetch(`/api/integrations/${provider}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credentials }) })
      const body = await response.json()
      if (!response.ok) throw new Error(body?.error?.message ?? "Não foi possível salvar a integração.")
      setStatuses(current => [...current.filter(item => item.provider !== provider), body])
      form.reset()
      setMessage({ type: "ok", text: "Configuração criptografada e salva. Os valores secretos não serão exibidos novamente." })
    } catch (error) { setMessage({ type: "error", text: error instanceof Error ? error.message : "Falha ao salvar." }) }
    finally { setSaving(null) }
  }

  return <Card>
    <CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="size-5 text-primary" />Central de credenciais do cliente</CardTitle><p className="text-sm text-muted-foreground">Configure cada canal com dados da sua própria conta. Senhas pessoais nunca são solicitadas.</p></CardHeader>
    <CardContent className="space-y-5">
      {message && <Alert variant={message.type === "error" ? "destructive" : "default"}><ShieldCheck className="size-4" /><AlertTitle>{message.type === "ok" ? "Configuração salva" : "Revise os dados"}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert>}
      <Tabs defaultValue="google">
        <TabsList className="grid w-full grid-cols-2"><TabsTrigger value="google">Google Growth</TabsTrigger><TabsTrigger value="instagram">Instagram</TabsTrigger></TabsList>
        {(["google", "instagram"] as Provider[]).map(provider => {
          const status = statuses.find(item => item.provider === provider)
          return <TabsContent value={provider} key={provider} className="mt-5">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-muted/30 p-4">
              <div><p className="font-medium">{provider === "google" ? "Google Ads, GA4 e Data Manager" : "Instagram Messaging"}</p><p className="mt-1 text-xs text-muted-foreground">{help[provider].text}</p></div>
              <Badge variant={status ? "secondary" : "outline"}>{status ? "Configurado" : "Aguardando dados"}</Badge>
            </div>
            <form className="space-y-5" onSubmit={event => { event.preventDefault(); void save(provider, event.currentTarget) }} autoComplete="off">
              <div className="grid gap-4 md:grid-cols-2">{fields[provider].map(field => <div className="grid gap-2" key={field.name}><Label htmlFor={`${provider}-${field.name}`}>{field.label}{field.required ? " *" : ""}</Label><Input id={`${provider}-${field.name}`} name={field.name} type={field.secret ? "password" : "text"} required={field.required} placeholder={status?.configured_fields.includes(field.name) ? "Já configurado — digite para substituir" : field.placeholder} autoComplete="new-password" /></div>)}</div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4"><Button asChild type="button" variant="outline"><a href={help[provider].href} target="_blank" rel="noreferrer">Como gerar meus dados <ExternalLink className="size-4" /></a></Button><Button type="submit" disabled={saving !== null}>{saving === provider ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}Salvar configuração</Button></div>
            </form>
          </TabsContent>
        })}
      </Tabs>
    </CardContent>
  </Card>
}
