"use client"

import { useMemo, useState } from "react"
import {
  Activity, AlertTriangle, Ban, CheckCircle2, CircleHelp, ExternalLink, Eye, EyeOff, FileClock,
  Check, Inbox, KeyRound, LayoutGrid, LoaderCircle, LockOpen, LogOut, Mail, MessageCircle, MoreHorizontal, RefreshCw, Search, ServerCog, ShieldCheck, Trash2, UserPlus, UsersRound, Workflow, XCircle,
} from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { IntegrationSettings } from "@/components/app-shell/integration-settings"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AdminService, AdminSnapshot, AdminUser } from "@/lib/admin/types"
import { MODULES, type ModuleKey } from "@/lib/modules"
import { cn } from "@/lib/utils"

const statusPresentation = {
  operational: { label: "Funcionando", icon: CheckCircle2, className: "border-emerald-500/20 bg-emerald-500/10 text-emerald-500" },
  attention: { label: "Atenção", icon: AlertTriangle, className: "border-amber-500/20 bg-amber-500/10 text-amber-500" },
  unavailable: { label: "Indisponível", icon: XCircle, className: "border-destructive/20 bg-destructive/10 text-destructive" },
  unknown: { label: "Não verificado", icon: CircleHelp, className: "border-border bg-muted/40 text-muted-foreground" },
} satisfies Record<AdminService["status"], { label: string; icon: typeof CheckCircle2; className: string }>

function formatDate(value: string | null) {
  if (!value) return "Nunca"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "Não informado" : new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo",
  }).format(date)
}

type MailerFindResult = "connected" | "denied" | "state_error" | "token_error" | "validation_error" | "save_error" | "error"

export function AdminConsole({ initialSnapshot, mailerFindResult }: { initialSnapshot: AdminSnapshot; mailerFindResult?: MailerFindResult }) {
  const [snapshot, setSnapshot] = useState(initialSnapshot)
  const [refreshing, setRefreshing] = useState(false)
  const [resetting, setResetting] = useState<string | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [dialog, setDialog] = useState<{ kind: "password" | "delete"; user: AdminUser } | null>(null)
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [confirmEmail, setConfirmEmail] = useState("")
  const [acting, setActing] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newUser, setNewUser] = useState<{ open: boolean; name: string; login: string; password: string; modules: ModuleKey[] }>({ open: false, name: "", login: "", password: "", modules: ["leads"] })
  const [moduleDialog, setModuleDialog] = useState<{ user: AdminUser; modules: ModuleKey[] } | null>(null)
  const operational = snapshot.services.filter((service) => service.status === "operational").length
  const grouped = useMemo(() => Object.groupBy(snapshot.services, (service) => service.category), [snapshot.services])

  async function refresh() {
    setRefreshing(true); setMessage(null)
    try {
      const response = await fetch("/api/admin/overview", { cache: "no-store" })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? "Falha ao sincronizar.")
      setSnapshot(body)
      setMessage({ ok: true, text: "Usuários, serviços e auditoria foram sincronizados." })
    } catch (error) {
      setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao sincronizar." })
    } finally { setRefreshing(false) }
  }

  async function resetPassword(user: AdminUser) {
    setResetting(user.id); setMessage(null)
    try {
      const response = await fetch("/api/admin/users/reset-password", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: user.email }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? "Falha ao enviar a recuperação.")
      setMessage({ ok: true, text: body.message })
    } catch (error) {
      setMessage({ ok: false, text: error instanceof Error ? error.message : "Falha ao enviar a recuperação." })
    } finally { setResetting(null) }
  }

  /** Password, sign-out, block/unblock and delete (Administração → Usuários). */
  async function manage(user: AdminUser, action: "password" | "sign_out" | "block" | "unblock" | "delete", extra: Record<string, string> = {}) {
    setActing(user.id); setMessage(null)
    try {
      const response = await fetch(`/api/admin/users/${user.id}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, ...extra }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? "Não foi possível concluir a ação.")
      setMessage({ ok: true, text: body.message })
      setDialog(null); setPassword(""); setConfirmEmail(""); setShowPassword(false)
      if (action === "delete") setSnapshot((current) => ({ ...current, users: current.users.filter((item) => item.id !== user.id) }))
      if (action === "block" || action === "unblock") setSnapshot((current) => ({ ...current, users: current.users.map((item) => item.id === user.id ? { ...item, blocked: action === "block" } : item) }))
    } catch (error) {
      setMessage({ ok: false, text: error instanceof Error ? error.message : "Não foi possível concluir a ação." })
    } finally { setActing(null) }
  }

  /** Administração → Usuários → Módulos: what this account sees in the module selector. */
  async function saveModules() {
    if (!moduleDialog) return
    const { user, modules } = moduleDialog
    setActing(user.id); setMessage(null)
    try {
      const response = await fetch(`/api/admin/users/${user.id}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "modules", modules }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? "Não foi possível salvar os módulos.")
      setSnapshot((current) => ({ ...current, users: current.users.map((item) => item.id === user.id ? { ...item, modules: body.modules } : item) }))
      setModuleDialog(null)
      setMessage({ ok: true, text: body.message })
    } catch (error) {
      setMessage({ ok: false, text: error instanceof Error ? error.message : "Não foi possível salvar os módulos." })
    } finally { setActing(null) }
  }

  async function createUser() {
    setCreating(true); setMessage(null)
    try {
      const response = await fetch("/api/admin/users", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newUser.name, login: newUser.login, password: newUser.password, modules: newUser.modules }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? "Não foi possível criar a conta.")
      setSnapshot((current) => ({ ...current, users: [body.user, ...current.users] }))
      setNewUser({ open: false, name: "", login: "", password: "", modules: ["leads"] }); setShowPassword(false)
      setMessage({ ok: true, text: body.message })
    } catch (error) {
      setMessage({ ok: false, text: error instanceof Error ? error.message : "Não foi possível criar a conta." })
      setNewUser((current) => ({ ...current, open: false }))
    } finally { setCreating(false) }
  }

  return <div className="space-y-6">
    <section className="relative overflow-hidden rounded-[28px] border bg-card px-5 py-6 shadow-[var(--shadow-2)] sm:px-7">
      <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-primary/10 blur-3xl" />
      <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div><div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-primary"><ShieldCheck className="size-4" />Acesso exclusivo</div><h1 className="kiara-editorial text-3xl sm:text-4xl">Central administrativa</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">Controle usuários, conexões, motores de pesquisa e saúde da plataforma em um único lugar.</p></div>
        <Button type="button" variant="outline" onClick={() => void refresh()} disabled={refreshing} className="shrink-0"><RefreshCw className={cn(refreshing && "animate-spin")} />Sincronizar tudo</Button>
      </div>
      <div className="relative mt-6 grid gap-3 sm:grid-cols-3">
        <Metric icon={UsersRound} label="Usuários" value={String(snapshot.users.length)} />
        <Metric icon={Activity} label="Serviços ativos" value={`${operational}/${snapshot.services.length}`} />
        <Metric icon={FileClock} label="Eventos recentes" value={String(snapshot.auditEvents.length)} />
      </div>
    </section>

    {message && <Alert variant={message.ok ? "default" : "destructive"} className={message.ok ? "border-emerald-500/20 bg-emerald-500/5" : undefined}>{message.ok ? <CheckCircle2 /> : <AlertTriangle />}<AlertTitle>{message.ok ? "Operação concluída" : "Não foi possível concluir"}</AlertTitle><AlertDescription>{message.text}</AlertDescription></Alert>}
    {snapshot.notices.map((notice) => <Alert key={notice}><CircleHelp /><AlertTitle>Informação do diagnóstico</AlertTitle><AlertDescription>{notice}</AlertDescription></Alert>)}

    <Tabs defaultValue={mailerFindResult ? "integrations" : "overview"} className="space-y-5">
      <TabsList style={{ height: "auto" }} className="grid w-full grid-cols-2 gap-1 rounded-2xl border bg-card p-1.5 sm:grid-cols-4">
        <TabsTrigger className="min-h-10 rounded-xl" value="overview">Visão geral</TabsTrigger>
        <TabsTrigger className="min-h-10 rounded-xl" value="users">Usuários</TabsTrigger>
        <TabsTrigger className="min-h-10 rounded-xl" value="integrations">APIs e conexões</TabsTrigger>
        <TabsTrigger className="min-h-10 rounded-xl" value="logs">Logs</TabsTrigger>
      </TabsList>

      <TabsContent value="overview" className="space-y-5">
        {Object.entries(grouped).map(([category, services]) => services?.length ? <Card key={category} className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5"><CardTitle className="text-base">{category}</CardTitle><CardDescription>Estado observado em {formatDate(snapshot.generatedAt)}.</CardDescription></CardHeader><CardContent className="divide-y p-0">{services.map((service) => <ServiceRow key={service.id} service={service} />)}</CardContent></Card> : null)}
      </TabsContent>

      <TabsContent value="users"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="flex flex-col gap-4 border-b p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6"><div><CardTitle>Usuários da aplicação</CardTitle><CardDescription className="mt-1.5">Controle total das contas: escolher os módulos de cada pessoa, criar, trocar a senha, desconectar de todos os aparelhos, bloquear o acesso ou excluir.</CardDescription></div><Button type="button" className="shrink-0" disabled={creating} onClick={() => { setShowPassword(false); setNewUser({ open: true, name: "", login: "", password: "", modules: ["leads"] }) }}>{creating ? <LoaderCircle className="animate-spin" /> : <UserPlus />}Novo usuário</Button></CardHeader><CardContent className="p-0">
        {snapshot.users.length ? <div className="divide-y">{snapshot.users.map((user) => <div key={user.id} className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-6"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="truncate font-semibold">{user.name}</p>{user.isAdmin && <Badge className="bg-primary/15 text-primary">Administrador</Badge>}{user.blocked && <Badge className="bg-destructive/15 text-destructive">Bloqueado</Badge>}</div><p className="mt-1 truncate text-sm text-muted-foreground">{user.email}</p><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"><span>{user.provider}</span><span>Último acesso: {formatDate(user.lastSignInAt)}</span><span>Criado em: {formatDate(user.createdAt)}</span></div><ModuleChips user={user} /></div><div className="flex flex-wrap items-center gap-2">
          {!user.isAdmin ? <Button type="button" variant="outline" disabled={acting !== null} onClick={() => setModuleDialog({ user, modules: [...user.modules] })}><LayoutGrid />Módulos</Button> : null}
          <Button type="button" variant="outline" disabled={acting !== null} onClick={() => { setPassword(""); setShowPassword(false); setDialog({ kind: "password", user }) }}><KeyRound />Trocar senha</Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button type="button" variant="outline" disabled={acting !== null || resetting !== null} aria-label={`Gerenciar ${user.email}`}>{acting === user.id || resetting === user.id ? <LoaderCircle className="animate-spin" /> : <MoreHorizontal />}Gerenciar</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
              <DropdownMenuItem onSelect={() => void manage(user, "sign_out")}><LogOut />Desconectar de todos os aparelhos</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void resetPassword(user)}><Mail />Enviar e-mail para redefinir senha</DropdownMenuItem>
              {!user.isAdmin ? <>
                <DropdownMenuSeparator />
                {user.blocked
                  ? <DropdownMenuItem onSelect={() => void manage(user, "unblock")}><LockOpen />Desbloquear acesso</DropdownMenuItem>
                  : <DropdownMenuItem variant="destructive" onSelect={() => void manage(user, "block")}><Ban />Bloquear acesso</DropdownMenuItem>}
                <DropdownMenuItem variant="destructive" onSelect={() => { setConfirmEmail(""); setDialog({ kind: "delete", user }) }}><Trash2 />Excluir conta</DropdownMenuItem>
              </> : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div></div>)}</div> : <div className="p-8 text-center text-sm text-muted-foreground">Nenhum usuário pôde ser carregado. Revise a configuração do Supabase Admin.</div>}
      </CardContent></Card></TabsContent>

      <TabsContent value="integrations" className="space-y-6">
        <Card className="gap-0 overflow-hidden border-primary/20 py-0"><CardHeader className="border-b p-5 sm:p-6"><div className="flex items-start gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary"><KeyRound className="size-4" /></span><div><CardTitle>Credenciais por workspace</CardTitle><CardDescription className="mt-1">Configure diretamente abaixo. Os segredos são criptografados pelo backend e nunca retornam para o navegador.</CardDescription></div></div></CardHeader><CardContent className="p-5 sm:p-6"><IntegrationSettings adminMode mailerFindResult={mailerFindResult} /></CardContent></Card>
        <Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Configuração global da infraestrutura</CardTitle><CardDescription>Chaves que alteram toda a plataforma ficam no cofre do ambiente, separadas das credenciais de cada cliente.</CardDescription></CardHeader><CardContent className="grid gap-3 p-5 sm:p-6 lg:grid-cols-2">{snapshot.services.filter((service) => service.category === "Infraestrutura" || service.status !== "operational").map((service) => <div key={service.id} className="rounded-2xl border bg-background/40 p-4"><div className="flex items-start justify-between gap-3"><p className="font-semibold">{service.name}</p><StatusBadge status={service.status} /></div><p className="mt-2 text-sm leading-5 text-muted-foreground">{service.detail}</p><code className="mt-3 block break-words rounded-lg bg-muted/50 px-3 py-2 text-[11px] text-foreground/80">{service.configuration}</code></div>)}</CardContent><div className="flex flex-col gap-3 border-t bg-muted/20 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6"><p className="max-w-2xl text-xs leading-5 text-muted-foreground">Por segurança, valores globais nunca são exibidos nesta página. Alterações no cofre exigem uma nova implantação do serviço correspondente.</p><Button asChild variant="outline" className="shrink-0"><a href="https://vercel.com/dashboard" target="_blank" rel="noreferrer">Abrir cofre da Vercel<ExternalLink /></a></Button></div></Card>
      </TabsContent>

      <TabsContent value="logs"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Logs e auditoria</CardTitle><CardDescription>Eventos de negócio sem conteúdo de mensagens, senhas ou chaves secretas.</CardDescription></CardHeader><CardContent className="p-0">{snapshot.auditEvents.length ? <div className="divide-y">{snapshot.auditEvents.map((event) => <div key={event.id} className="grid gap-2 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-6"><div className="min-w-0"><p className="truncate font-mono text-xs font-semibold">{event.action}</p><p className="mt-1 truncate text-xs text-muted-foreground">{event.resourceType} · ref. {event.correlationId}</p></div><time className="text-xs text-muted-foreground">{formatDate(event.occurredAt)}</time></div>)}</div> : <div className="grid min-h-52 place-items-center p-8 text-center"><div><FileClock className="mx-auto size-8 text-muted-foreground" /><p className="mt-3 font-medium">Nenhum evento de auditoria publicado</p><p className="mt-1 max-w-md text-sm text-muted-foreground">Use os estados da Visão geral para o diagnóstico atual. Os logs detalhados continuam protegidos no provedor de infraestrutura.</p></div></div>}</CardContent></Card></TabsContent>
    </Tabs>
      <Dialog open={newUser.open} onOpenChange={(open) => { if (!open) setNewUser((current) => ({ ...current, open: false })) }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Novo usuário</DialogTitle><DialogDescription>A conta já nasce liberada para entrar. Use um e-mail ou só um nome de usuário (ex.: kiara02), que vira o login.</DialogDescription></DialogHeader>
          <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void createUser() }}>
            <Input value={newUser.name} onChange={(event) => setNewUser({ ...newUser, name: event.target.value })} maxLength={80} placeholder="Nome (opcional)" aria-label="Nome" autoComplete="off" />
            <Input value={newUser.login} onChange={(event) => setNewUser({ ...newUser, login: event.target.value })} maxLength={254} placeholder="E-mail ou nome de usuário" aria-label="E-mail ou nome de usuário" autoComplete="off" autoCapitalize="none" spellCheck={false} autoFocus />
            <div className="flex items-center gap-2"><Input type={showPassword ? "text" : "password"} value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} minLength={6} maxLength={72} autoComplete="new-password" placeholder="Senha (mínimo 6 caracteres)" aria-label="Senha" />
              <Button type="button" variant="ghost" size="icon" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Esconder senha" : "Mostrar senha"}>{showPassword ? <EyeOff /> : <Eye />}</Button></div>
            <ModulePicker value={newUser.modules} onChange={(modules) => setNewUser((current) => ({ ...current, modules }))} />
            <DialogFooter><Button type="button" variant="ghost" onClick={() => setNewUser((current) => ({ ...current, open: false }))}>Cancelar</Button><Button type="submit" disabled={creating || newUser.login.trim().length < 2 || newUser.password.length < 6}>{creating ? <LoaderCircle className="animate-spin" /> : <UserPlus />}Criar conta</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog open={dialog?.kind === "password"} onOpenChange={(open) => { if (!open) setDialog(null) }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Trocar senha</DialogTitle><DialogDescription>Nova senha para {dialog?.user.email}. A senha antiga para de funcionar na hora e os aparelhos conectados precisam entrar de novo.</DialogDescription></DialogHeader>
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (dialog) void manage(dialog.user, "password", { password }) }}>
          <div className="flex items-center gap-2"><Input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={6} maxLength={72} autoComplete="new-password" placeholder="Nova senha (mínimo 6 caracteres)" aria-label="Nova senha" autoFocus />
            <Button type="button" variant="ghost" size="icon" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Esconder senha" : "Mostrar senha"}>{showPassword ? <EyeOff /> : <Eye />}</Button></div>
          <DialogFooter><Button type="button" variant="ghost" onClick={() => setDialog(null)}>Cancelar</Button><Button type="submit" disabled={password.length < 6 || acting !== null}>{acting ? <LoaderCircle className="animate-spin" /> : <KeyRound />}Salvar nova senha</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
    <Dialog open={moduleDialog !== null} onOpenChange={(open) => { if (!open) setModuleDialog(null) }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Módulos da conta</DialogTitle><DialogDescription>O que {moduleDialog?.user.email} vê na tela inicial e consegue abrir. Ao tirar um módulo, a pessoa é desconectada para a mudança valer na hora.</DialogDescription></DialogHeader>
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void saveModules() }}>
          {moduleDialog ? <ModulePicker value={moduleDialog.modules} onChange={(modules) => setModuleDialog((current) => current && { ...current, modules })} /> : null}
          <DialogFooter><Button type="button" variant="ghost" onClick={() => setModuleDialog(null)}>Cancelar</Button><Button type="submit" disabled={acting !== null}>{acting ? <LoaderCircle className="animate-spin" /> : <Check />}Salvar módulos</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
    <Dialog open={dialog?.kind === "delete"} onOpenChange={(open) => { if (!open) setDialog(null) }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Excluir conta</DialogTitle><DialogDescription>A conta de {dialog?.user.email} é excluída e a pessoa não consegue mais entrar. Isso não pode ser desfeito. Para confirmar, digite o e-mail da conta.</DialogDescription></DialogHeader>
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (dialog) void manage(dialog.user, "delete") }}>
          <Input value={confirmEmail} onChange={(event) => setConfirmEmail(event.target.value)} placeholder={dialog?.user.email} aria-label="E-mail da conta" autoComplete="off" />
          <DialogFooter><Button type="button" variant="ghost" onClick={() => setDialog(null)}>Cancelar</Button><Button type="submit" variant="destructive" disabled={confirmEmail.trim().toLowerCase() !== dialog?.user.email.toLowerCase() || acting !== null}>{acting ? <LoaderCircle className="animate-spin" /> : <Trash2 />}Excluir conta</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
}

const MODULE_ICONS: Record<ModuleKey, typeof Search> = { leads: Search, whatsapp: MessageCircle, chat: Inbox, automation: Workflow }

/** Turns each module on or off for an account; works with any number of modules. */
function ModulePicker({ value, onChange }: { value: ModuleKey[]; onChange: (modules: ModuleKey[]) => void }) {
  const toggle = (key: ModuleKey) => onChange(value.includes(key) ? value.filter((item) => item !== key) : MODULES.map((item) => item.key).filter((item) => item === key || value.includes(item)))
  return <fieldset className="space-y-2">
    <legend className="mb-2 text-sm font-medium">Módulos liberados</legend>
    <div className="grid gap-2">{MODULES.map(({ key, label, description }) => {
      const on = value.includes(key)
      const Icon = MODULE_ICONS[key]
      return <button key={key} type="button" role="switch" aria-checked={on} onClick={() => toggle(key)} className={cn("flex min-h-14 items-center gap-3 rounded-xl border p-3 text-left transition-colors", on ? "border-primary/60 bg-primary/10" : "hover:bg-muted/40")}>
        <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", on ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}><Icon className="size-4" aria-hidden="true" /></span>
        <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{label}</span><span className="block truncate text-xs text-muted-foreground">{description}</span></span>
        <span className={cn("grid size-5 shrink-0 place-items-center rounded-md border", on ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40")} aria-hidden="true">{on ? <Check className="size-3.5" /> : null}</span>
      </button>
    })}</div>
    {!value.length ? <p className="text-xs text-amber-500">Sem nenhum módulo, a conta entra mas não vê nada até você liberar.</p> : null}
  </fieldset>
}

function ModuleChips({ user }: { user: AdminUser }) {
  if (user.isAdmin) return <p className="mt-2 text-xs text-muted-foreground">Todos os módulos</p>
  if (!user.modules.length) return <p className="mt-2 text-xs text-amber-500">Nenhum módulo liberado</p>
  return <div className="mt-2 flex flex-wrap gap-1.5">{MODULES.filter(({ key }) => user.modules.includes(key)).map(({ key, label }) => <Badge key={key} variant="outline" className="font-normal">{label.replace("KIARA ", "")}</Badge>)}</div>
}

function Metric({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) {
  return <div className="flex items-center gap-3 rounded-2xl border bg-background/45 p-4"><span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="size-4" /></span><div><p className="text-xl font-semibold">{value}</p><p className="text-xs text-muted-foreground">{label}</p></div></div>
}

function StatusBadge({ status }: { status: AdminService["status"] }) {
  const presentation = statusPresentation[status]
  const Icon = presentation.icon
  return <Badge variant="outline" className={presentation.className}><Icon />{presentation.label}</Badge>
}

function ServiceRow({ service }: { service: AdminService }) {
  return <div className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-5"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{service.name}</p><StatusBadge status={service.status} /></div><p className="mt-1 text-sm leading-5 text-muted-foreground">{service.detail}</p><p className="mt-2 flex items-start gap-2 text-[11px] text-muted-foreground"><ServerCog className="mt-0.5 size-3 shrink-0" />{service.configuration}</p></div></div>
}
