import { Radar } from "lucide-react"

import { PageHeader } from "@/components/app-shell/page-header"
import { Card, CardContent } from "@/components/ui/card"

export default function HunterPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Investigação permitida" title="Hunter" description="Sinais reais e públicos serão exibidos aqui quando a fonte oficial estiver conectada." /><Card><CardContent className="grid min-h-72 place-items-center p-8 text-center"><div><Radar className="mx-auto size-7 text-muted-foreground" /><h2 className="mt-4 font-semibold">Nenhuma fonte conectada</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Conecte uma integração autorizada para iniciar pesquisas.</p></div></CardContent></Card></div>
}
