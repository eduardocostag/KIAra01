import { PageHeader } from "@/components/app-shell/page-header"
import { SettingsForm } from "@/components/app-shell/settings-form"
export default function SettingsPage(){return <div className="space-y-6"><PageHeader eyebrow="Workspace" title="Configurações comerciais" description="Defina identidade, oferta, mensagens e cadência usadas em todo o ciclo de prospecção."/><SettingsForm/></div>}
