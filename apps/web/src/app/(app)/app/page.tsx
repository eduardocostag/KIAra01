import Link from "next/link"
import { ArrowRight, MessageCircle, Radio, ShieldCheck } from "lucide-react"

import { PageHeader } from "@/components/app-shell/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getInboxDTO } from "@/lib/api/inbox"

export default async function DashboardPage() {
  const { apiAvailable, conversations } = await getInboxDTO()
    .then((inbox) => ({ apiAvailable: true, conversations: inbox.conversations }))
    .catch(() => ({ apiAvailable: false, conversations: [] }))
  const unread = conversations.reduce((total, item) => total + item.unread, 0)

  return <div className="space-y-6">
    <PageHeader eyebrow="Hoje · operação B2C" title="O que precisa de você" description="Dados reais do seu workspace, organizados para a próxima decisão humana." />
    <Card className="overflow-hidden border-primary/25 bg-primary/[0.045] shadow-sm"><CardContent className="relative p-5 sm:p-7"><div aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-primary" /><div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between"><div><p className="text-sm font-medium text-primary">Inbox em tempo real</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">{apiAvailable ? (conversations.length ? `${conversations.length} conversa${conversations.length === 1 ? "" : "s"} ativa${conversations.length === 1 ? "" : "s"}` : "Nenhuma conversa recebida") : "API temporariamente indisponível"}</h2><p className="mt-2 text-sm text-muted-foreground">{unread ? `${unread} mensagem${unread === 1 ? "" : "s"} inbound para revisar.` : "As novas DMs aparecerão aqui após a conexão do Instagram."}</p></div><Button asChild size="lg"><Link href="/app/inbox">Abrir Inbox <ArrowRight /></Link></Button></div></CardContent></Card>
    <div className="grid gap-5 md:grid-cols-3"><StatusCard icon={MessageCircle} title="Conversas" value={apiAvailable ? String(conversations.length) : "—"} detail={apiAvailable ? "Carregadas da API" : "Conexão indisponível"} /><StatusCard icon={Radio} title="Instagram" value="Pendente" detail="Aguardando conexão Meta" /><StatusCard icon={ShieldCheck} title="Aprovação humana" value="Obrigatória" detail="Sem envio automático" /></div>
  </div>
}

function StatusCard({ icon: Icon, title, value, detail }: { icon: typeof Radio; title: string; value: string; detail: string }) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Icon className="size-4 text-primary" />{title}</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{value}</p><p className="mt-1 text-xs text-muted-foreground">{detail}</p></CardContent></Card>
}
