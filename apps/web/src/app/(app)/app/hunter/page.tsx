import { PageHeader } from "@/components/app-shell/page-header"
import { HunterClient } from "./hunter-client"

export default function HunterPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Inteligência comercial com controle humano" title="Hunter" description="Encontre sinais públicos em múltiplas fontes para prospecção B2C e B2B." /><HunterClient /></div>
}
