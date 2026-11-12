import Link from "next/link"
import { ArrowRight, Headphones, MessageCircle, MonitorCog, Radar, Workflow, Sparkles } from "lucide-react"
import { PageHeader } from "@/components/app-shell/page-header"
import { Badge } from "@/components/ui/badge"
import type { ModuleKey, PlatformContext } from "@/lib/platform/contracts"
import styles from "./platform.module.css"

const icons = { leads: Radar, whatsapp: MessageCircle, atendimento: Headphones, ti: MonitorCog, intelligence: Sparkles } satisfies Record<ModuleKey, typeof Radar>

export function PlatformOverview({ context }: { context: PlatformContext }) {
  return <div className={styles.content}>
    <PageHeader eyebrow="KIARA" title="Sua operação, por módulos" description="Acesse os módulos disponíveis para a sua empresa e acompanhe a preparação das novas áreas." />
    <div className={styles.phase}><Workflow className="size-5 shrink-0" aria-hidden="true" /><p><strong>Estrutura da plataforma</strong><span>Leads, WhatsApp e KIARA Chat têm áreas próprias. TI está em preparação. Cada módulo informa suas conexões e dependências.</span></p></div>
    {context.modules.length ? <section aria-label="Módulos disponíveis" className={styles.moduleGrid}>
      {context.modules.map((module) => {
        const Icon = icons[module.key]
        const chat = ["atendimento", "intelligence"].includes(module.key)
        return <Link key={module.key} href={module.key === "whatsapp" ? "/app/whatsapp" : chat ? "/app/chat" : module.href} className={styles.moduleCard}>
          <div className={styles.cardTop}><span className={styles.moduleIcon}><Icon className="size-6" aria-hidden="true" /></span><Badge variant={module.status === "operational" || module.key === "whatsapp" || chat ? "secondary" : "outline"}>{module.key === "whatsapp" || chat ? "Acessar módulo" : module.status_label}</Badge></div>
          <h2>{module.key === "atendimento" ? "KIARA Chat" : module.name}</h2><p>{module.description}</p>
          <span className={styles.cardAction}>{module.key === "leads" ? "Abrir Leads" : module.key === "whatsapp" ? "Abrir WhatsApp" : chat ? "Abrir KIARA Chat" : "Conhecer a estrutura"}<ArrowRight className="size-4" aria-hidden="true" /></span>
        </Link>
      })}
    </section> : <section className={styles.empty}><h2>Nenhum módulo liberado</h2><p>Consulte o administrador para revisar os acessos da sua empresa.</p></section>}
    <section className={styles.scope} aria-labelledby="platform-scope-title"><h2 id="platform-scope-title">Uma conta, áreas organizadas</h2><p>Os acessos acima foram confirmados para {context.organization.name}. Cada módulo apresenta seu estado de preparação e as conexões existentes.</p></section>
  </div>
}
