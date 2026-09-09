import { CopilotIntro } from "@/components/app-shell/copilot-intro"
import { PageHeader } from "@/components/app-shell/page-header"
import { HunterClient } from "./hunter-client"

export default function HunterPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Prospecção · Hunter" title="Encontre os leads certos." description="Pesquise seu público, verifique os critérios e leve as oportunidades para o seu CRM." /><CopilotIntro title="Conte quem você quer encontrar." description="Eu transformo sua intenção em uma pesquisa organizada e mostro o que está acontecendo em cada etapa." /><HunterClient /></div>
}
