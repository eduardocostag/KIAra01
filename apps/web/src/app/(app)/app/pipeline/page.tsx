import { PageHeader } from "@/components/app-shell/page-header"
import { PipelineBoard } from "@/components/app-shell/pipeline-board"

export default function PipelinePage() {
  return <div className="space-y-6">
    <PageHeader eyebrow="Jornada comercial" title="Pipeline" description="Priorize a próxima ação, compare prazos e altere etapas sem depender de arrastar cards." />
    <PipelineBoard />
  </div>
}
