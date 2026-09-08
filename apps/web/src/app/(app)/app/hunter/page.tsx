import { Sparkles } from "lucide-react"

import { HunterResults } from "@/components/app-shell/hunter-results"
import { PageHeader } from "@/components/app-shell/page-header"
import { Button } from "@/components/ui/button"

export default function HunterPage() {
  return <div className="space-y-6">
    <PageHeader eyebrow="Investigação permitida" title="Hunter" description="Compare oportunidades inbound, sinais públicos e bloqueios sem confundir interesse com autorização de contato." actions={<div className="text-right"><Button disabled><Sparkles aria-hidden="true" />Nova pesquisa</Button><p className="mt-1 text-xs text-muted-foreground">Indisponível na demonstração</p></div>} />
    <HunterResults />
  </div>
}
