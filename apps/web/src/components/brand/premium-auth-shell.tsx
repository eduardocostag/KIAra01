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

        <p className="auth-footnote text-xs text-white/35">Kiara Intelligence · Operação protegida</p>
      </section>

      <section className="auth-form-panel relative grid place-items-center border-l border-white/8 px-4 py-8 sm:px-5 sm:py-10">
        <div className="w-full max-w-md sm:rounded-[26px] sm:border sm:border-white/10 sm:bg-[#1d1a26]/90 sm:p-8 sm:shadow-[0_32px_90px_rgb(0_0_0/.38)]">
          <div className="auth-mobile-hero mb-6 flex flex-col items-center text-center sm:hidden">
            <KiaraOrb className="auth-hero-orb" size="lg" active />
            <Link href="/" className="mt-2 px-2 py-2 text-[15px] font-semibold tracking-[.32em] text-white" aria-label="Ir para a página inicial da Kiara">KIARA</Link>
          </div>
          <div className="mb-8 hidden sm:block lg:hidden"><KiaraBrand inverse /></div>
          {children}
        </div>
      </section>
    </main>
  )
}
