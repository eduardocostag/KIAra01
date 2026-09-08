import { Columns3 } from "lucide-react"

import { PageHeader } from "@/components/app-shell/page-header"
import { Card, CardContent } from "@/components/ui/card"

export default function PipelinePage() {
  return <div className="space-y-6"><PageHeader eyebrow="Jornada comercial" title="Pipeline" description="Oportunidades reais qualificadas a partir das conversas do workspace." /><Card><CardContent className="grid min-h-72 place-items-center p-8 text-center"><div><Columns3 className="mx-auto size-7 text-muted-foreground" /><h2 className="mt-4 font-semibold">Nenhuma oportunidade sincronizada</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">As oportunidades aparecerão aqui quando conversas reais forem recebidas e qualificadas.</p></div></CardContent></Card></div>
}
