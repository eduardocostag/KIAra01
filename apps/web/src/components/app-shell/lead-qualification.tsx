import { temperatureLabels } from "@/lib/api/inbox-contract"
import type { PipelineEntry } from "@/lib/api/pipeline"

export function LeadQualification({ qualification }: { qualification: PipelineEntry["qualification"] }) {
  if (!qualification) return <p className="mt-4 text-xs text-muted-foreground">Nível comercial ainda não classificado. Novas mensagens atualizam os sinais do lead.</p>
  return <div className="mt-5 rounded-xl border bg-primary/5 p-4 text-left"><div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold">{temperatureLabels[qualification.temperature] ?? "Não classificado"}</p><span className="text-xs font-semibold text-primary">{qualification.score}/100</span></div>{qualification.reasons?.length ? <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-muted-foreground">{qualification.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul> : null}{qualification.recommendation && <p className="mt-3 text-xs">{qualification.recommendation}</p>}</div>
}
