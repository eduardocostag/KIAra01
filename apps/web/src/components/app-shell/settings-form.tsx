"use client"

import { useEffect, useState, type ReactNode } from "react"
import { Clock3, LoaderCircle, MessageSquareText, Save, ShieldCheck } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { salesRequest, type SalesProfile, templateLabels } from "@/lib/api/sales"

export function SettingsForm() {
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => { void salesRequest<SalesProfile>("/api/sales/profile").then(setProfile).catch((error) => setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao carregar." })) }, [])

  async function save() {
    if (!profile) return
    setBusy(true); setMessage(null)
    try {
      const saved = await salesRequest<SalesProfile>("/api/sales/profile", { method: "PUT", body: JSON.stringify(profile) })
      setProfile(saved); setMessage({ ok: true, text: "Configurações e modelos salvos para este workspace." })
    } catch (error) { setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao salvar." }) }
    finally { setBusy(false) }
  }

  if (!profile) return <Card><CardContent className="flex min-h-48 items-center justify-center"><LoaderCircle className="size-5 animate-spin" /><span className="ml-2">Carregando configurações…</span></CardContent></Card>
  return <div className="space-y-5">
    {message ? <Alert variant={message.ok ? "default" : "destructive"}><ShieldCheck /><AlertTitle>{message.ok ? "Tudo certo" : "Não foi possível salvar"}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert> : null}
    <Tabs defaultValue="operation" className="gap-5">
      <TabsList className="h-auto flex-wrap"><TabsTrigger value="operation"><ShieldCheck />Operação</TabsTrigger><TabsTrigger value="templates"><MessageSquareText />Modelos</TabsTrigger><TabsTrigger value="cadence"><Clock3 />Cadência</TabsTrigger></TabsList>
      <TabsContent value="operation"><Card><CardHeader><CardTitle>Identidade comercial</CardTitle><CardDescription>Esses dados personalizam as abordagens preparadas pela Kiara.</CardDescription></CardHeader><CardContent className="grid gap-5 md:grid-cols-2">
        <Field label="Nome do negócio"><Input value={profile.business_name} onChange={(e) => setProfile({ ...profile, business_name: e.target.value })} maxLength={160} /></Field>
        <Field label="Nome do remetente"><Input value={profile.sender_name} onChange={(e) => setProfile({ ...profile, sender_name: e.target.value })} maxLength={160} /></Field>
        <Field label="Oferta principal" wide><Textarea value={profile.offer} onChange={(e) => setProfile({ ...profile, offer: e.target.value })} className="min-h-28" maxLength={4000} /></Field>
        <Field label="Tom de atendimento" wide><Input value={profile.tone} onChange={(e) => setProfile({ ...profile, tone: e.target.value })} maxLength={500} /></Field>
      </CardContent></Card></TabsContent>
      <TabsContent value="templates"><Card><CardHeader><CardTitle>Biblioteca de abordagens</CardTitle><CardDescription>Variáveis aceitas: {'{remetente}'}, {'{nome}'}, {'{nicho}'}, {'{cidade}'} e {'{oferta}'}.</CardDescription></CardHeader><CardContent className="grid gap-5">
        {Object.entries(profile.templates).map(([key, value]) => <Field key={key} label={templateLabels[key] || key}><Textarea value={value} onChange={(e) => setProfile({ ...profile, templates: { ...profile.templates, [key]: e.target.value } })} className="min-h-24" maxLength={20000} /></Field>)}
      </CardContent></Card></TabsContent>
      <TabsContent value="cadence"><Card><CardHeader><CardTitle>Cadência e horário</CardTitle><CardDescription>A Kiara agenda lembretes; o envio continua dependendo de confirmação.</CardDescription></CardHeader><CardContent className="grid gap-5 sm:grid-cols-3">
        <Field label="Follow-up após (horas)"><Input type="number" min={1} max={720} value={profile.follow_up_hours} onChange={(e) => setProfile({ ...profile, follow_up_hours: Number(e.target.value) })} /></Field>
        <Field label="Início dos contatos"><Input type="time" value={profile.contact_start} onChange={(e) => setProfile({ ...profile, contact_start: e.target.value })} /></Field>
        <Field label="Fim dos contatos"><Input type="time" value={profile.contact_end} onChange={(e) => setProfile({ ...profile, contact_end: e.target.value })} /></Field>
      </CardContent></Card></TabsContent>
    </Tabs>
    <div className="sticky bottom-4 flex justify-end"><Button onClick={save} disabled={busy} size="lg" className="shadow-lg">{busy ? <LoaderCircle className="animate-spin" /> : <Save />}Salvar configurações</Button></div>
  </div>
}

function Field({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return <div className={`grid gap-2 ${wide ? "md:col-span-2" : ""}`}><Label>{label}</Label>{children}</div>
}
