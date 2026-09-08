import { PageHeader } from "@/components/app-shell/page-header"
import { SettingsForm } from "@/components/app-shell/settings-form"
export default function SettingsPage(){return <div className="space-y-6"><PageHeader eyebrow="Workspace" title="Configurações" description="Ajuste operação, tom e autonomia. Mudanças críticas exigirão validação do servidor na versão conectada."/><SettingsForm/></div>}
