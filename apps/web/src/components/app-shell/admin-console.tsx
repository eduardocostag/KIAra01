"use client"

import { useMemo, useState } from "react"
import {
  Activity, AlertTriangle, CheckCircle2, CircleHelp, ExternalLink, FileClock,
  KeyRound, LoaderCircle, RefreshCw, ServerCog, ShieldCheck, UsersRound, XCircle,
} from "lucide-react"
import { IntegrationSettings } from "@/components/app-shell/integration-settings"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AdminService, AdminSnapshot, AdminUser } from "@/lib/admin/types"
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

      <TabsContent value="users"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Usuários da aplicação</CardTitle><CardDescription>Consulte acessos e envie um link seguro para o próprio usuário definir uma nova senha.</CardDescription></CardHeader><CardContent className="p-0">
        {snapshot.users.length ? <div className="divide-y">{snapshot.users.map((user) => <div key={user.id} className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-6"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="truncate font-semibold">{user.name}</p>{user.isAdmin && <Badge className="bg-primary/15 text-primary">Administrador</Badge>}</div><p className="mt-1 truncate text-sm text-muted-foreground">{user.email}</p><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"><span>{user.provider}</span><span>Último acesso: {formatDate(user.lastSignInAt)}</span><span>Criado em: {formatDate(user.createdAt)}</span></div></div><Button type="button" variant="outline" disabled={resetting !== null} onClick={() => void resetPassword(user)}>{resetting === user.id ? <LoaderCircle className="animate-spin" /> : <KeyRound />}Enviar redefinição</Button></div>)}</div> : <div className="p-8 text-center text-sm text-muted-foreground">Nenhum usuário pôde ser carregado. Revise a configuração do Supabase Admin.</div>}
      </CardContent></Card></TabsContent>

      <TabsContent value="integrations" className="space-y-6">
        <Card className="gap-0 overflow-hidden border-primary/20 py-0"><CardHeader className="border-b p-5 sm:p-6"><div className="flex items-start gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary"><KeyRound className="size-4" /></span><div><CardTitle>Credenciais por workspace</CardTitle><CardDescription className="mt-1">Configure diretamente abaixo. Os segredos são criptografados pelo backend e nunca retornam para o navegador.</CardDescription></div></div></CardHeader><CardContent className="p-5 sm:p-6"><IntegrationSettings adminMode mailerFindResult={mailerFindResult} /></CardContent></Card>
        <Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Configuração global da infraestrutura</CardTitle><CardDescription>Chaves que alteram toda a plataforma ficam no cofre do ambiente, separadas das credenciais de cada cliente.</CardDescription></CardHeader><CardContent className="grid gap-3 p-5 sm:p-6 lg:grid-cols-2">{snapshot.services.filter((service) => service.category === "Infraestrutura" || service.status !== "operational").map((service) => <div key={service.id} className="rounded-2xl border bg-background/40 p-4"><div className="flex items-start justify-between gap-3"><p className="font-semibold">{service.name}</p><StatusBadge status={service.status} /></div><p className="mt-2 text-sm leading-5 text-muted-foreground">{service.detail}</p><code className="mt-3 block break-words rounded-lg bg-muted/50 px-3 py-2 text-[11px] text-foreground/80">{service.configuration}</code></div>)}</CardContent><div className="flex flex-col gap-3 border-t bg-muted/20 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6"><p className="max-w-2xl text-xs leading-5 text-muted-foreground">Por segurança, valores globais nunca são exibidos nesta página. Alterações no cofre exigem uma nova implantação do serviço correspondente.</p><Button asChild variant="outline" className="shrink-0"><a href="https://vercel.com/dashboard" target="_blank" rel="noreferrer">Abrir cofre da Vercel<ExternalLink /></a></Button></div></Card>
      </TabsContent>

      <TabsContent value="logs"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b p-5 sm:p-6"><CardTitle>Logs e auditoria</CardTitle><CardDescription>Eventos de negócio sem conteúdo de mensagens, senhas ou chaves secretas.</CardDescription></CardHeader><CardContent className="p-0">{snapshot.auditEvents.length ? <div className="divide-y">{snapshot.auditEvents.map((event) => <div key={event.id} className="grid gap-2 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-6"><div className="min-w-0"><p className="truncate font-mono text-xs font-semibold">{event.action}</p><p className="mt-1 truncate text-xs text-muted-foreground">{event.resourceType} · ref. {event.correlationId}</p></div><time className="text-xs text-muted-foreground">{formatDate(event.occurredAt)}</time></div>)}</div> : <div className="grid min-h-52 place-items-center p-8 text-center"><div><FileClock className="mx-auto size-8 text-muted-foreground" /><p className="mt-3 font-medium">Nenhum evento de auditoria publicado</p><p className="mt-1 max-w-md text-sm text-muted-foreground">Use os estados da Visão geral para o diagnóstico atual. Os logs detalhados continuam protegidos no provedor de infraestrutura.</p></div></div>}</CardContent></Card></TabsContent>
    </Tabs>
  </div>
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
