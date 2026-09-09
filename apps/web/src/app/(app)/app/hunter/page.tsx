import { PageHeader } from "@/components/app-shell/page-header"
import { HunterClient } from "./hunter-client"

export default function HunterPage() {
  return <div className="space-y-6"><PageHeader eyebrow="PROSPECÇÃO / HUNTER" title="Encontre os leads certos." description="Pesquise seu público, verifique os critérios e leve as oportunidades para o seu CRM." /><HunterClient /></div>
}
