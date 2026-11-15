import { TodayQueue } from "@/components/app-shell/today-queue"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function TodayQueuePage() {
  const entries = await getPipelineDTO().catch(() => null)
  return <div className="mx-auto w-full max-w-6xl space-y-6">
    <header>
      <h1 className="text-3xl font-medium tracking-tight">Fila de hoje</h1>
      <p className="mt-1 text-sm text-muted-foreground">Um lead por vez: a Kiara escreve, você revisa e envia pelo seu WhatsApp com um toque.</p>
    </header>
    {entries ? <TodayQueue entries={entries} /> : <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">Não foi possível carregar seus leads agora. Atualize a página em instantes.</p>}
  </div>
}
