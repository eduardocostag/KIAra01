import type { ReactNode } from "react"
import Link from "next/link"
import { KiaraBrand } from "./kiara-brand"
import { KiaraOrb } from "./kiara-orb"

export function PremiumAuthShell({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children: ReactNode }) {
  return (
    <main className="marketing-shell auth-shell relative grid min-h-svh overflow-hidden lg:grid-cols-[minmax(0,1fr)_minmax(27rem,.88fr)]">
      <section className="auth-visual relative hidden flex-col lg:flex">
        <Link href="/" className="auth-brand w-fit" aria-label="Ir para a página inicial da Kiara">
          <KiaraBrand inverse />
        </Link>

        <div className="auth-hero">
          <div className="auth-orb-stage">
            <KiaraOrb className="auth-hero-orb" size="lg" active />
          </div>
          <div className="auth-copy">
            <p className="eyebrow">{eyebrow}</p>
            <h1 className="kiara-editorial auth-title text-white">{title}</h1>
            <p className="auth-description text-white/60">{description}</p>
          </div>
        </div>

        <p className="auth-footnote text-xs text-white/35">Kiara Lead Intelligence · Operação protegida</p>
      </section>

      <section className="auth-form-panel relative grid place-items-center border-l border-white/8 px-5 py-8 sm:py-10">
        <div className="w-full max-w-md rounded-[26px] border border-white/10 bg-[#1d1a26]/90 p-6 shadow-[0_32px_90px_rgb(0_0_0/.38)] sm:p-8">
          <div className="mb-8 lg:hidden"><KiaraBrand inverse /></div>
          {children}
        </div>
      </section>
    </main>
  )
}
