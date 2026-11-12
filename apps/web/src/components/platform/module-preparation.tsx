import Link from "next/link"
import { ArrowRight, CircleDashed, ClipboardList, Link2, ShieldCheck } from "lucide-react"
import { PageHeader } from "@/components/app-shell/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ModuleKey, PlatformModule } from "@/lib/platform/contracts"
import styles from "./platform.module.css"

type Area = Readonly<{ title: string; description: string }>
const areas: Record<Exclude<ModuleKey, "leads">, readonly Area[]> = {
  whatsapp: [
    { title: "Integrações", description: "Espaço para acompanhar as conexões do canal e suas permissões." },
    { title: "Conversas", description: "Área reservada para organizar conversas e encaminhamentos do módulo." },
    { title: "Indicadores", description: "Espaço para apresentar volume e evolução quando o módulo estiver conectado." },
  ],
  atendimento: [
    { title: "Triagem", description: "Organização inicial das solicitações recebidas." },
    { title: "Atendimento humano", description: "Preparação da passagem de contexto para a equipe." },
    { title: "Histórico", description: "Área reservada para os registros de cada atendimento." },
    { title: "Distribuição", description: "Estrutura para filas e responsáveis." },
    { title: "Indicadores e relatórios", description: "Espaço para acompanhar a operação após a integração." },
  ],
  intelligence: [
    { title: "Conversa com IA", description: "Acesse o KIARA Chat para consultar os modelos e recursos conectados." },
    { title: "Execução local", description: "Tarefas dependem de ferramentas reais, revisão do plano e autorização." },
  ],
  ti: [
    { title: "Tickets", description: "Estrutura para registrar e acompanhar solicitações de suporte." },
    { title: "Prioridades", description: "Área reservada para critérios de impacto e urgência." },
    { title: "SLA", description: "Espaço para os prazos e compromissos de atendimento." },
    { title: "Distribuição", description: "Organização futura de equipes e responsáveis técnicos." },
    { title: "Alertas de infraestrutura", description: "Espaço para alertas e contexto dos ambientes após a conexão de uma fonte." },
    { title: "Relatórios", description: "Estrutura para acompanhar solicitações e evolução do suporte." },
  ],
}

export function ModulePreparation({ module }: { module: PlatformModule }) {
  if (module.key === "leads") return null
  return <div className={styles.content}>
    <PageHeader eyebrow="KIARA · Plataforma" title={module.name} description={module.description}
      actions={<Badge variant="outline">Em preparação</Badge>} />
    <div className={styles.phase}><CircleDashed className="size-5 shrink-0" aria-hidden="true" /><p><strong>Estrutura disponível para consulta</strong><span>As áreas abaixo ainda não executam ações nem iniciam conexões. A integração deste módulo será preparada em uma próxima etapa.</span></p></div>
    <section aria-label={`Áreas de ${module.name}`} className={styles.areaGrid}>{areas[module.key].map((area) => <article key={area.title} className={styles.areaCard}>
      <ClipboardList className="size-5 text-primary" aria-hidden="true" /><h2>{area.title}</h2><p>{area.description}</p><span className={styles.preparing}><CircleDashed className="size-3.5" aria-hidden="true" />Em preparação</span>
    </article>)}</section>
    <section className={styles.verification} aria-labelledby="module-connection-title"><ShieldCheck className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><h2 id="module-connection-title">Conexão e indicadores</h2><p>Não verificada nesta etapa</p><span>Esta página não consulta sessões, não envia mensagens e não executa comandos.</span></div></section>
    {module.key === "whatsapp" ? <section className={styles.scope} aria-labelledby="existing-whatsapp-title"><h2 id="existing-whatsapp-title"><Link2 className="size-4" aria-hidden="true" />Configurações existentes</h2><p>As configurações de canais permanecem na área de integrações. Acessar essa área não ativa este módulo.</p><Button asChild variant="outline"><Link href="/app/settings/integrations">Consultar integrações<ArrowRight className="size-4" aria-hidden="true" /></Link></Button></section> : null}
    {module.key === "atendimento" ? <section className={styles.scope} aria-labelledby="existing-inbox-title"><h2 id="existing-inbox-title">Caixa de entrada existente</h2><p>O atendimento já disponível na Kiara continua na caixa de entrada atual. Este novo módulo está em preparação.</p><Button asChild variant="outline"><Link href="/app/inbox">Abrir caixa de entrada existente<ArrowRight className="size-4" aria-hidden="true" /></Link></Button></section> : null}
    {module.key === "ti" ? <section className={styles.scope}><h2>Integrações futuras</h2><p>Tiflux, GLPI e outras fontes poderão ser configuradas em uma próxima etapa. Nenhum sistema está conectado por este módulo.</p></section> : null}
    <Link href="/app/platform" className={styles.backLink}>Voltar à plataforma</Link>
  </div>
}
