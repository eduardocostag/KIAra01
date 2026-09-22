"use client"

import { useEffect, useState, type ReactNode } from "react"
import { useClerk, useUser } from "@clerk/nextjs"
import { Building2, CheckCircle2, Database, KeyRound, LoaderCircle, LogOut, Mail, MessageSquareText, Plus, Save, ShieldCheck, Trash2, UserRound } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { salesRequest, type SalesProfile, templateLabels } from "@/lib/api/sales"

type Section = "account" | "operation" | "templates" | "data"
const sections = {
  account: { label: "Minha conta", description: "Perfil, senha e sessão", icon: UserRound },
  operation: { label: "Identidade", description: "Quem fala e o que oferece", icon: Building2 },
  templates: { label: "Mensagens", description: "Textos para cada situação", icon: MessageSquareText },
  data: { label: "Dados", description: "Reiniciar dados de Leads", icon: Database },
} satisfies Record<Section, { label: string; description: string; icon: typeof Building2 }>

type ResetResponse = {
  status: "reset"
  deleted: { leads: number; pipeline_entries: number; searches: number; conversations: number; activities: number }
}

const templateHelp: Record<string, string> = {
  first_contact: "Mensagem inicial para um novo contato.", no_website: "Abordagem para perfis sem site informado.",
  website_opportunity: "Use quando houver uma oportunidade técnica no site.", instagram_opportunity: "Abordagem baseada na presença pública do Instagram.",
  follow_up: "Lembrete breve quando ainda não houve resposta.", reactivation: "Retome uma conversa que ficou parada.",
  objection: "Resposta-base para dúvidas ou resistência.", interest: "Continuação para quem demonstrou interesse.",
}
const builtInTemplates = new Set(Object.keys(templateHelp))

function customTemplateLabel(key: string) {
  return key.replace(/^custom_/, "").replace(/_/g, " ").replace(/\b\p{L}/gu, (letter) => letter.toUpperCase())
}

function authErrorMessage(error: unknown) {
  if (error && typeof error === "object" && "errors" in error && Array.isArray(error.errors)) {
    const first = error.errors[0]
    if (first && typeof first === "object") {
      const message = "longMessage" in first ? first.longMessage : "message" in first ? first.message : null
      if (typeof message === "string" && message.trim()) return message
    }
  }
  return error instanceof Error ? error.message : "Não foi possível concluir a operação."
}

export function SettingsForm() {
  const { isLoaded: userLoaded, user } = useUser()
  const { signOut } = useClerk()
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [section, setSection] = useState<Section>("operation")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string; title?: string } | null>(null)
  const [newMessageOpen, setNewMessageOpen] = useState(false)
  const [newMessageName, setNewMessageName] = useState("")
  const [newMessageBody, setNewMessageBody] = useState("")
  const [resetOpen, setResetOpen] = useState(false)
  const [resetConfirmation, setResetConfirmation] = useState("")
  const [resetBusy, setResetBusy] = useState(false)
  const [accountFirstName, setAccountFirstName] = useState<string | null>(null)
  const [accountLastName, setAccountLastName] = useState<string | null>(null)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [accountBusy, setAccountBusy] = useState<"profile" | "password" | "logout" | null>(null)
  const [accountMessage, setAccountMessage] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => { void salesRequest<SalesProfile>("/api/sales/profile").then(setProfile).catch((error) => setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao carregar." })) }, [])
  const resolvedFirstName = accountFirstName ?? user?.firstName ?? ""
  const resolvedLastName = accountLastName ?? user?.lastName ?? ""

  async function save() {
    if (!profile) return
    setBusy(true); setMessage(null)
    try {
      const update = {
        business_name: profile.business_name,
        sender_name: profile.sender_name,
        offer: profile.offer,
        tone: profile.tone,
        follow_up_hours: profile.follow_up_hours,
        contact_start: profile.contact_start,
        contact_end: profile.contact_end,
        templates: profile.templates,
      }
      const saved = await salesRequest<SalesProfile>("/api/sales/profile", { method: "PUT", body: JSON.stringify(update) })
      setProfile(saved); setMessage({ ok: true, text: "Alterações salvas neste workspace." })
    } catch (error) { setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao salvar." }) }
    finally { setBusy(false) }
  }

  function addMessage() {
    if (!profile || !newMessageName.trim() || !newMessageBody.trim()) return
    const slug = newMessageName.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 70) || "mensagem"
    let key = `custom_${slug}`
    let suffix = 2
    while (profile.templates[key]) key = `custom_${slug}_${suffix++}`
    setProfile({ ...profile, templates: { ...profile.templates, [key]: newMessageBody.trim() } })
    setNewMessageName(""); setNewMessageBody(""); setNewMessageOpen(false)
  }

  function removeMessage(key: string) {
    if (!profile || builtInTemplates.has(key)) return
    const templates = { ...profile.templates }
    delete templates[key]
    setProfile({ ...profile, templates })
  }

  async function resetWorkspace() {
    if (resetConfirmation !== "ZERAR") return
    setResetBusy(true); setMessage(null)
    try {
      const result = await salesRequest<ResetResponse>("/api/workspace/commercial-data", {
        method: "DELETE",
        body: JSON.stringify({ confirmation: resetConfirmation }),
      })
      setResetOpen(false); setResetConfirmation("")
      setMessage({
        ok: true,
        title: "Dados de Leads zerados",
        text: `${result.deleted.leads} lead${result.deleted.leads === 1 ? "" : "s"} e ${result.deleted.pipeline_entries} registro${result.deleted.pipeline_entries === 1 ? "" : "s"} de acompanhamento foram removidos.`,
      })
    } catch (error) {
      setMessage({ ok: false, title: "Não foi possível zerar os dados", text: error instanceof Error ? error.message : "Falha ao reiniciar o workspace." })
    } finally {
      setResetBusy(false)
    }
  }

  async function saveAccountProfile() {
    if (!user) return
    setAccountBusy("profile"); setAccountMessage(null)
    try {
      await user.update({ firstName: resolvedFirstName.trim(), lastName: resolvedLastName.trim() })
      setAccountMessage({ ok: true, text: "Nome atualizado com segurança." })
    } catch (error) {
      setAccountMessage({ ok: false, text: authErrorMessage(error) })
    } finally {
      setAccountBusy(null)
    }
  }

  async function changePassword() {
    if (!user) return
    if (newPassword.length < 8) { setAccountMessage({ ok: false, text: "A nova senha deve ter pelo menos 8 caracteres." }); return }
    if (newPassword !== confirmPassword) { setAccountMessage({ ok: false, text: "A confirmação não corresponde à nova senha." }); return }
    setAccountBusy("password"); setAccountMessage(null)
    try {
      await user.updatePassword({ currentPassword: user.passwordEnabled ? currentPassword : undefined, newPassword, signOutOfOtherSessions: true })
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("")
      setAccountMessage({ ok: true, text: "Senha atualizada. As outras sessões foram encerradas." })
    } catch (error) {
      setAccountMessage({ ok: false, text: authErrorMessage(error) })
    } finally {
      setAccountBusy(null)
    }
  }

  async function logout() {
    setAccountBusy("logout"); setAccountMessage(null)
    try {
      await signOut({ redirectUrl: "/sign-in" })
    } catch (error) {
      setAccountBusy(null)
      setAccountMessage({ ok: false, text: authErrorMessage(error) })
    }
  }

  if (!profile) return <Card className="overflow-hidden"><CardContent className="flex min-h-64 items-center justify-center text-sm text-muted-foreground"><LoaderCircle className="size-5 animate-spin" /><span className="ml-3">Carregando configurações…</span></CardContent></Card>

  return <div className="space-y-5">
    {message ? <Alert variant={message.ok ? "default" : "destructive"} className={message.ok ? "border-emerald-500/20 bg-emerald-500/5" : undefined}>{message.ok ? <CheckCircle2 /> : <ShieldCheck />}<AlertTitle>{message.title || (message.ok ? "Configurações atualizadas" : "Não foi possível salvar")}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert> : null}
    <Tabs value={section} onValueChange={(value) => { const next = value as Section; if (next === "account" && user) { setAccountFirstName(user.firstName ?? ""); setAccountLastName(user.lastName ?? ""); setAccountMessage(null) } setSection(next); setMessage(null) }} orientation="vertical" className="grid items-start gap-5 lg:grid-cols-[250px_minmax(0,1fr)]">
      <aside className="lg:sticky lg:top-7"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5"><CardTitle className="text-sm">Áreas de configuração</CardTitle><CardDescription className="text-xs leading-5">Escolha uma seção para editar.</CardDescription></CardHeader><CardContent className="p-2">
        <TabsList className="grid h-auto w-full gap-1 bg-transparent p-0">{(Object.entries(sections) as [Section, typeof sections[Section]][]).map(([value, item]) => { const Icon = item.icon; return <TabsTrigger key={value} value={value} className="h-auto w-full justify-start gap-3 rounded-xl px-3 py-3.5 text-left data-active:bg-primary/12 data-active:text-foreground"><span className="grid size-9 shrink-0 place-items-center rounded-lg border bg-background text-primary"><Icon className="size-4" /></span><span className="min-w-0"><strong className="block text-sm font-semibold">{item.label}</strong><small className="mt-0.5 block truncate text-[11px] font-normal text-muted-foreground">{item.description}</small></span></TabsTrigger> })}</TabsList>
      </CardContent></Card></aside>

      <div className="min-w-0 space-y-4">
        <TabsContent value="account"><div className="space-y-4">
          {accountMessage ? <Alert variant={accountMessage.ok ? "default" : "destructive"} className={accountMessage.ok ? "border-emerald-500/20 bg-emerald-500/5" : undefined}>{accountMessage.ok ? <CheckCircle2 /> : <ShieldCheck />}<AlertTitle>{accountMessage.ok ? "Conta atualizada" : "Não foi possível atualizar a conta"}</AlertTitle><AlertDescription>{accountMessage.text}</AlertDescription></Alert> : null}
          <Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Perfil do usuário</CardTitle><CardDescription>Dados pessoais vinculados à sua conta de acesso.</CardDescription></CardHeader><CardContent className="grid gap-5 p-5 sm:p-6 md:grid-cols-2">
            <Field id="account-first-name" label="Nome" help="Como você será identificado na Kiara."><Input id="account-first-name" value={resolvedFirstName} onChange={(event) => setAccountFirstName(event.target.value)} disabled={!userLoaded || !user || accountBusy !== null} maxLength={100} autoComplete="given-name" /></Field>
            <Field id="account-last-name" label="Sobrenome" help="Complemento do seu nome de usuário."><Input id="account-last-name" value={resolvedLastName} onChange={(event) => setAccountLastName(event.target.value)} disabled={!userLoaded || !user || accountBusy !== null} maxLength={100} autoComplete="family-name" /></Field>
            <Field id="account-email" label="E-mail" help="Endereço usado para entrar na sua conta." wide><div className="relative"><Mail className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" /><Input id="account-email" value={user?.primaryEmailAddress?.emailAddress ?? ""} readOnly className="pl-10 text-muted-foreground" /></div></Field>
            <div className="flex justify-end md:col-span-2"><Button type="button" onClick={() => void saveAccountProfile()} disabled={!userLoaded || !user || accountBusy !== null || !resolvedFirstName.trim()}>{accountBusy === "profile" ? <LoaderCircle className="animate-spin" /> : <Save />}Salvar perfil</Button></div>
          </CardContent></Card>

          <Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Senha</CardTitle><CardDescription>{user?.passwordEnabled ? "Atualize sua senha e encerre as demais sessões abertas." : "Defina uma senha para também entrar com e-mail e senha."}</CardDescription></CardHeader><CardContent className="grid gap-5 p-5 sm:p-6 md:grid-cols-2">
            {user?.passwordEnabled ? <Field id="current-password" label="Senha atual" help="Necessária para confirmar sua identidade." wide><Input id="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} disabled={accountBusy !== null} autoComplete="current-password" /></Field> : null}
            <Field id="new-password" label="Nova senha" help="Use pelo menos 8 caracteres."><Input id="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} disabled={accountBusy !== null} autoComplete="new-password" minLength={8} /></Field>
            <Field id="confirm-password" label="Confirmar senha" help="Digite novamente a nova senha."><Input id="confirm-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} disabled={accountBusy !== null} autoComplete="new-password" minLength={8} /></Field>
            <div className="flex justify-end md:col-span-2"><Button type="button" variant="outline" onClick={() => void changePassword()} disabled={!user || accountBusy !== null || !newPassword || !confirmPassword || (Boolean(user.passwordEnabled) && !currentPassword)}>{accountBusy === "password" ? <LoaderCircle className="animate-spin" /> : <KeyRound />}Alterar senha</Button></div>
          </CardContent></Card>

          <Card className="gap-0 overflow-hidden py-0"><CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"><div><h3 className="font-semibold">Encerrar sessão</h3><p className="mt-1 text-sm text-muted-foreground">Saia com segurança desta conta neste dispositivo.</p></div><Button type="button" variant="outline" className="shrink-0" disabled={accountBusy !== null} onClick={() => void logout()}>{accountBusy === "logout" ? <LoaderCircle className="animate-spin" /> : <LogOut />}Fazer logoff</Button></CardContent></Card>
        </div></TabsContent>

        <TabsContent value="operation"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Dados da sua operação</CardTitle><CardDescription>A Kiara usa estas informações para preparar mensagens coerentes com seu negócio.</CardDescription></CardHeader><CardContent className="grid gap-6 p-5 sm:p-6 md:grid-cols-2">
          <Field id="business-name" label="Nome do negócio" help="Como sua empresa deve ser apresentada."><Input id="business-name" value={profile.business_name} onChange={(e) => setProfile({ ...profile, business_name: e.target.value })} maxLength={160} placeholder="Ex.: Agência Aurora" /></Field>
          <Field id="sender-name" label="Nome do remetente" help="Pessoa que assina as mensagens."><Input id="sender-name" value={profile.sender_name} onChange={(e) => setProfile({ ...profile, sender_name: e.target.value })} maxLength={160} placeholder="Ex.: Eduardo" /></Field>
          <Field id="main-offer" label="Oferta principal" help="Explique o que você vende e qual resultado entrega." wide><Textarea id="main-offer" value={profile.offer} onChange={(e) => setProfile({ ...profile, offer: e.target.value })} className="min-h-32 resize-y" maxLength={4000} placeholder="Ex.: Ajudamos clínicas a gerar oportunidades qualificadas por meio de…" /></Field>
          <Field id="service-tone" label="Tom de atendimento" help="Descreva como a Kiara deve escrever." wide><Input id="service-tone" value={profile.tone} onChange={(e) => setProfile({ ...profile, tone: e.target.value })} maxLength={500} placeholder="Ex.: consultivo, direto, cordial e sem exageros" /></Field>
        </CardContent></Card></TabsContent>

        <TabsContent value="templates"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Biblioteca de mensagens</CardTitle><CardDescription className="mt-1">Personalize os textos usados em cada situação. As variáveis são substituídas no momento da abordagem.</CardDescription></div><Button type="button" onClick={() => setNewMessageOpen(true)} className="shrink-0"><Plus />Nova mensagem</Button></div></CardHeader><CardContent className="p-5 sm:p-6">
          <div className="mb-6 flex flex-wrap gap-2 rounded-xl border bg-muted/30 p-3" aria-label="Variáveis disponíveis"><span className="mr-1 self-center text-xs text-muted-foreground">Variáveis:</span>{["remetente", "nome", "nicho", "cidade", "oferta"].map((variable) => <code key={variable} className="rounded-md border bg-background px-2 py-1 text-[11px] text-primary">{`{${variable}}`}</code>)}</div>
          <div className="grid gap-4 xl:grid-cols-2">{Object.entries(profile.templates).map(([key, value]) => <Field key={key} id={`template-${key}`} label={templateLabels[key] || customTemplateLabel(key)} help={templateHelp[key] || "Modelo personalizado criado por você."} action={!builtInTemplates.has(key) ? <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground hover:text-destructive" onClick={() => removeMessage(key)} aria-label={`Remover ${customTemplateLabel(key)}`}><Trash2 className="size-4" /></Button> : null}><Textarea id={`template-${key}`} value={value} onChange={(e) => setProfile({ ...profile, templates: { ...profile.templates, [key]: e.target.value } })} className="min-h-36 resize-y" maxLength={20000} /></Field>)}</div>
        </CardContent></Card></TabsContent>

        <TabsContent value="data"><Card className="gap-0 overflow-hidden border-destructive/25 py-0"><CardHeader className="border-b border-destructive/15 p-5 sm:p-6"><CardTitle>Reiniciar dados comerciais</CardTitle><CardDescription>Comece do zero sem apagar sua identidade, mensagens ou integrações.</CardDescription></CardHeader><CardContent className="p-5 sm:p-6"><div className="flex flex-col gap-5 rounded-xl border border-destructive/20 bg-destructive/[.04] p-5 sm:flex-row sm:items-center sm:justify-between"><div className="max-w-2xl"><h3 className="font-semibold">Zerar dados de Leads</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">Remove todos os leads, etapas de acompanhamento, atividades, conversas e pesquisas deste workspace. Esta ação não pode ser desfeita.</p></div><Button type="button" variant="destructive" className="shrink-0" onClick={() => { setResetConfirmation(""); setResetOpen(true) }}><Trash2 />Zerar dados</Button></div></CardContent></Card></TabsContent>

        {section === "operation" || section === "templates" ? <div className="sticky bottom-4 z-10 flex flex-col gap-3 rounded-2xl border bg-background/92 p-3 shadow-xl backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3 px-1"><UserRound className="size-4 text-primary" /><p className="text-xs text-muted-foreground">As alterações valem para todo o workspace.</p></div><Button onClick={save} disabled={busy} size="lg" className="min-w-48">{busy ? <LoaderCircle className="animate-spin" /> : <Save />}Salvar alterações</Button></div> : null}
      </div>
    </Tabs>
    <Dialog open={newMessageOpen} onOpenChange={setNewMessageOpen}>
      <DialogContent className="sm:max-w-xl"><DialogHeader><DialogTitle>Adicionar nova mensagem</DialogTitle><DialogDescription>Crie um modelo para uma situação específica. Ele ficará disponível ao preparar uma abordagem.</DialogDescription></DialogHeader><div className="grid gap-5 py-2"><div className="grid gap-2"><Label htmlFor="new-message-name">Nome do modelo</Label><Input id="new-message-name" value={newMessageName} onChange={(event) => setNewMessageName(event.target.value)} maxLength={70} placeholder="Ex.: Retorno após orçamento" autoFocus /></div><div className="grid gap-2"><Label htmlFor="new-message-body">Mensagem</Label><Textarea id="new-message-body" value={newMessageBody} onChange={(event) => setNewMessageBody(event.target.value)} className="min-h-40 resize-y" maxLength={20000} placeholder="Escreva a mensagem e use variáveis como {nome} e {oferta}." /><p className="text-xs text-muted-foreground">Variáveis disponíveis: {'{remetente}'}, {'{nome}'}, {'{nicho}'}, {'{cidade}'} e {'{oferta}'}.</p></div></div><DialogFooter><Button type="button" variant="outline" onClick={() => setNewMessageOpen(false)}>Cancelar</Button><Button type="button" onClick={addMessage} disabled={!newMessageName.trim() || !newMessageBody.trim() || Object.keys(profile.templates).length >= 30}><Plus />Adicionar à biblioteca</Button></DialogFooter></DialogContent>
    </Dialog>
    <Dialog open={resetOpen} onOpenChange={(open) => { if (!resetBusy) { setResetOpen(open); if (!open) setResetConfirmation("") } }}>
      <DialogContent className="sm:max-w-lg"><DialogHeader><DialogTitle>Zerar dados de Leads?</DialogTitle><DialogDescription>Todos os dados comerciais deste workspace serão removidos definitivamente. Configurações, mensagens e integrações serão preservadas.</DialogDescription></DialogHeader><div className="grid gap-2 py-2"><Label htmlFor="reset-confirmation">Digite ZERAR para confirmar</Label><Input id="reset-confirmation" value={resetConfirmation} onChange={(event) => setResetConfirmation(event.target.value.toUpperCase())} autoComplete="off" disabled={resetBusy} placeholder="ZERAR" /></div><DialogFooter><Button type="button" variant="outline" disabled={resetBusy} onClick={() => setResetOpen(false)}>Cancelar</Button><Button type="button" variant="destructive" disabled={resetBusy || resetConfirmation !== "ZERAR"} onClick={() => void resetWorkspace()}>{resetBusy ? <LoaderCircle className="animate-spin" /> : <Trash2 />}Zerar definitivamente</Button></DialogFooter></DialogContent>
    </Dialog>
  </div>
}

function Field({ id, label, help, wide, action, children }: { id: string; label: string; help: string; wide?: boolean; action?: ReactNode; children: ReactNode }) {
  return <div className={`grid content-start gap-2 rounded-xl border bg-background/35 p-4 ${wide ? "md:col-span-2" : ""}`}><div className="flex items-start justify-between gap-3"><div><Label htmlFor={id} className="text-sm font-semibold">{label}</Label><p id={`${id}-help`} className="mt-1 text-xs leading-5 text-muted-foreground">{help}</p></div>{action}</div>{children}</div>
}
