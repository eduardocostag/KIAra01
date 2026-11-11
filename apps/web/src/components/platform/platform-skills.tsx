import Link from "next/link"
import { BookOpenCheck, CircleDashed, ShieldCheck } from "lucide-react"
import { PageHeader } from "@/components/app-shell/page-header"
import type { PlatformSkill } from "@/lib/platform/contracts"
import styles from "./platform.module.css"

const moduleLabels = {
  leads: "KIARA Leads",
  whatsapp: "KIARA WhatsApp",
  atendimento: "KIARA Atendimento",
  ti: "KIARA TI",
} as const

export function PlatformSkills({ skills }: { skills: readonly PlatformSkill[] }) {
  return <div className={styles.content}>
    <PageHeader
      eyebrow="KIARA · Plataforma"
      title="Catálogo de skills"
      description="Referências disponíveis para os módulos autorizados da sua empresa."
    />
    <div className={styles.phase}>
      <BookOpenCheck className="size-5 shrink-0" aria-hidden="true" />
      <p>
        <strong>Somente consulta</strong>
        <span>As skills são conteúdo de referência não confiável. Esta tela não executa instruções, ferramentas ou integrações.</span>
      </p>
    </div>
    {skills.length ? <section aria-label="Skills disponíveis" className={styles.skillGrid}>
      {skills.map((skill) => <article key={skill.name} className={styles.skillCard}>
        <div className={styles.cardTop}>
          <h2>{skill.name}</h2>
          <span className={styles.preparing}><CircleDashed className="size-3.5" aria-hidden="true" />Execução inativa</span>
        </div>
        <p>{skill.description}</p>
        <div className={styles.skillMeta} aria-label={`Módulos autorizados para ${skill.name}`}>
          {skill.modules.map((module) => <span key={module}>{moduleLabels[module]}</span>)}
          <span>Referência não confiável</span>
        </div>
      </article>)}
    </section> : <section className={styles.empty}>
      <h2>Nenhuma skill disponível</h2>
      <p>Não há referências autorizadas para os módulos habilitados nesta empresa.</p>
    </section>}
    <section className={styles.verification} aria-labelledby="skill-safety-title">
      <ShieldCheck className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <h2 id="skill-safety-title">Limites deste catálogo</h2>
        <p>O catálogo informa descrição, escopo de módulo e estado do executor. Dependências, permissões e ambiente de execução ainda não são verificados nesta etapa.</p>
      </div>
    </section>
    <Link href="/app/platform" className={styles.backLink}>Voltar à plataforma</Link>
  </div>
}
