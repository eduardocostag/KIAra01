import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, MessagesSquare, Radar, ShieldCheck, UsersRound } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { Button } from "@/components/ui/button"
import styles from "./competition.module.css"

export const metadata: Metadata = {
  title: "Concorrência | Kiara",
  description: "Inteligência competitiva e descoberta responsável de novas oportunidades.",
}

const capabilities = [
  { icon: UsersRound, label: "Mapear audiências" },
  { icon: MessagesSquare, label: "Identificar sinais de interesse" },
  { icon: ShieldCheck, label: "Qualificar antes do contato" },
]

export default function CompetitionPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p>Inteligência de mercado</p>
        <h1>Concorrência</h1>
      </header>

      <section className={styles.stage} aria-labelledby="competition-production-title">
        <div className={styles.ambient} aria-hidden="true">
          <span className={styles.orbitOne} />
          <span className={styles.orbitTwo} />
          <span className={styles.signalOne} />
          <span className={styles.signalTwo} />
        </div>

        <div className={styles.content}>
          <div className={styles.orbWrap} aria-hidden="true">
            <span className={styles.radarRing} />
            <KiaraOrb className={styles.orb} size="lg" active />
            <span className={styles.radarMark}><Radar /></span>
          </div>

          <span className={styles.status}><i />Em produção</span>
          <h2 id="competition-production-title">Uma nova visão sobre o seu mercado está sendo preparada.</h2>
          <p className={styles.description}>
            A Kiara reunirá sinais públicos de audiência e interesse para ajudar você a reconhecer novas oportunidades, avaliar sua aderência e decidir o melhor momento para iniciar uma abordagem.
          </p>

          <div className={styles.capabilities} aria-label="Recursos em preparação">
            {capabilities.map(({ icon: Icon, label }) => (
              <span key={label}><Icon aria-hidden="true" />{label}</span>
            ))}
          </div>

          <p className={styles.note}>Disponibilizaremos esta experiência após concluirmos as validações de qualidade, privacidade e segurança.</p>

          <Button asChild variant="outline" className={styles.backButton}>
            <Link href="/app/hunter"><ArrowLeft />Voltar ao Hunter</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}
