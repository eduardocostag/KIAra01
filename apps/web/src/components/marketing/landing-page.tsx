import Link from "next/link"
import { ArrowRight, ContactRound, Search, Workflow } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { SignalPreview } from "./signal-preview"

const features = [
  {
    icon: Search,
    title: "Encontre",
    copy: "Pesquise leads por perfil, localidade e fontes selecionadas.",
  },
  {
    icon: ContactRound,
    title: "Revise",
    copy: "Consulte os dados disponíveis em uma ficha organizada.",
  },
  {
    icon: Workflow,
    title: "Acompanhe",
    copy: "Organize etapas, atividades e follow-ups no Pipeline.",
  },
]

export function LandingPage() {
  return (
    <div className="marketing-shell min-h-svh overflow-hidden bg-background text-foreground">
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>

      <header className="marketing-header sticky top-0 z-40 border-b border-white/8 bg-[#0d0c16]/78 backdrop-blur-2xl">
        <nav aria-label="Navegação principal" className="mx-auto flex h-[72px] max-w-[1320px] items-center gap-6 px-5 sm:px-8">
          <Link href="/" className="rounded-xl focus-visible:outline-offset-4" aria-label="Kiara Lead Intelligence, início">
            <KiaraBrand inverse />
          </Link>
          <div className="ml-auto flex items-center gap-1.5">
            <Button asChild variant="ghost" className="h-10 px-3 text-white/72 hover:bg-white/8 hover:text-white">
              <Link href="/sign-in">Entrar</Link>
            </Button>
            <Button asChild className="h-10 rounded-[10px] px-4 shadow-[0_8px_28px_rgb(111_76_255/.18)]">
              <Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link>
            </Button>
          </div>
        </nav>
      </header>

      <main id="conteudo">
        <section className="marketing-hero relative mx-auto grid max-w-[1320px] items-center gap-14 px-5 pb-20 pt-16 sm:px-8 sm:pt-20 lg:min-h-[650px] lg:grid-cols-[0.88fr_1.12fr] lg:pb-24 lg:pt-20">
          <div className="marketing-aurora pointer-events-none absolute inset-0 -z-10" aria-hidden="true" />
          <div className="relative z-10 max-w-[570px]">
            <p className="eyebrow">Prospecção e organização comercial</p>
            <h1 className="hero-display mt-5 text-balance text-white">Encontre leads e avance com clareza.</h1>
            <p className="mt-6 max-w-[520px] text-pretty text-base leading-7 text-white/58 sm:text-[17px]">
              Da pesquisa ao Pipeline, a Kiara mantém oportunidades e próximos passos no mesmo lugar.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="h-12 rounded-xl px-6 shadow-[0_16px_45px_rgb(91_54_199/.22)]">
                <Link href="/sign-up">Começar agora <ArrowRight aria-hidden="true" /></Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-12 rounded-xl border-white/12 bg-white/[.025] px-6 text-white hover:bg-white/7 hover:text-white">
                <Link href="/sign-in">Já tenho uma conta</Link>
              </Button>
            </div>
          </div>
          <div className="relative z-10"><SignalPreview /></div>
        </section>

        <section id="produto" className="border-y border-white/8 bg-white/[0.015]">
          <div className="mx-auto grid max-w-[1320px] gap-px bg-white/8 sm:grid-cols-3">
            {features.map(({ icon: Icon, title, copy }) => (
              <article key={title} className="marketing-simple-feature bg-[#11101c] px-6 py-8 sm:px-8">
                <Icon className="size-5 text-primary" strokeWidth={1.7} aria-hidden="true" />
                <h2 className="mt-5 text-base font-semibold text-white">{title}</h2>
                <p className="mt-2 max-w-xs text-sm leading-6 text-white/46">{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-24">
          <div className="marketing-minimal-cta flex flex-col items-start justify-between gap-7 rounded-[24px] border border-white/10 p-7 sm:p-10 lg:flex-row lg:items-center">
            <div>
              <p className="eyebrow">Pronto para começar?</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-white">Faça sua primeira pesquisa.</h2>
              <p className="mt-3 text-sm text-white/48">Crie sua conta e configure seu workspace.</p>
            </div>
            <Button asChild size="lg" className="h-12 shrink-0 rounded-xl px-6"><Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link></Button>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/8">
        <div className="mx-auto flex max-w-[1320px] flex-col gap-4 px-5 py-7 text-xs text-white/34 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <KiaraBrand inverse />
          <span>© 2026 Kiara Lead Intelligence</span>
        </div>
      </footer>
    </div>
  )
}
