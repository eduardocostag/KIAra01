import Link from "next/link"
import {
  ArrowRight,
  Check,
  ChevronRight,
  ContactRound,
  MapPinned,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { SignalPreview } from "./signal-preview"

const productCuts = [
  {
    icon: Search,
    overline: "Hunter",
    title: "Pesquise o público certo.",
    copy: "Defina profissão, nicho e localidade, escolha as fontes e acompanhe os resultados em uma única tela.",
  },
  {
    icon: ContactRound,
    overline: "Leads",
    title: "Revise cada oportunidade.",
    copy: "Consulte telefone, Instagram, site, endereço e origem sempre que essas informações estiverem disponíveis.",
  },
  {
    icon: Workflow,
    overline: "Pipeline",
    title: "Avance com organização.",
    copy: "Classifique etapas, registre atividades e mantenha o histórico comercial de cada lead no seu workspace.",
  },
]

const steps = [
  { number: "01", title: "Defina sua busca", copy: "Informe o perfil, a região e as fontes que deseja consultar." },
  { number: "02", title: "Revise os resultados", copy: "Compare os dados encontrados e abra a ficha de cada lead." },
  { number: "03", title: "Organize o avanço", copy: "Mova oportunidades no Pipeline e registre o próximo contato." },
]

export function LandingPage() {
  return (
    <div className="marketing-shell min-h-svh overflow-hidden bg-background text-foreground">
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>

      <header className="marketing-header sticky top-0 z-40 border-b border-white/8 bg-[#0d0c16]/78 backdrop-blur-2xl">
        <nav aria-label="Navegação principal" className="mx-auto flex h-[76px] max-w-[1440px] items-center gap-6 px-5 sm:px-8">
          <Link href="/" className="rounded-xl focus-visible:outline-offset-4" aria-label="Kiara Lead Intelligence, início">
            <KiaraBrand inverse />
          </Link>
          <div className="ml-auto hidden items-center gap-8 lg:flex">
            <Link href="#produto" className="marketing-nav-link">Produto</Link>
            <Link href="#como-funciona" className="marketing-nav-link">Como funciona</Link>
            <Link href="#recursos" className="marketing-nav-link">Recursos</Link>
          </div>
          <div className="ml-auto flex items-center gap-1.5 lg:ml-4">
            <Button asChild variant="ghost" className="h-11 px-3 text-white hover:bg-white/8 hover:text-white">
              <Link href="/sign-in">Entrar</Link>
            </Button>
            <Button asChild className="h-11 rounded-[11px] px-4 shadow-[0_8px_28px_rgb(111_76_255/.22)] hover:bg-[var(--primary-hover)]">
              <Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link>
            </Button>
          </div>
        </nav>
      </header>

      <main id="conteudo">
        <section className="marketing-hero relative mx-auto grid max-w-[1440px] items-center gap-12 px-5 pb-20 pt-16 sm:px-8 sm:pt-24 lg:min-h-[760px] lg:grid-cols-[0.88fr_1.12fr] lg:gap-14 lg:pb-28 lg:pt-24">
          <div className="marketing-aurora pointer-events-none absolute inset-0 -z-10" aria-hidden="true" />
          <div className="marketing-dot-field pointer-events-none absolute -left-60 top-10 -z-10 size-[760px] opacity-50" aria-hidden="true" />
          <div className="relative z-10 max-w-[650px]">
            <div className="marketing-kicker"><Sparkles className="size-3.5" aria-hidden="true" /> Inteligência comercial em um só lugar</div>
            <h1 className="hero-display mt-7 text-balance text-white">Encontre bons leads. Organize cada próximo passo.</h1>
            <p className="mt-7 max-w-[590px] text-pretty text-[17px] leading-7 tracking-[-0.012em] text-white/62 sm:text-lg sm:leading-8">
              Pesquise oportunidades por nicho e região, revise os contatos encontrados e conduza seu Pipeline com clareza.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="h-13 rounded-xl px-7 shadow-[0_0_0_6px_oklch(0.735_0.16_273/0.08),0_18px_48px_rgb(92_56_210/.25)] hover:bg-[var(--primary-hover)]">
                <Link href="/sign-up">Começar agora <ArrowRight aria-hidden="true" /></Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-13 rounded-xl border-white/14 bg-white/4 px-7 text-white hover:bg-white/9 hover:text-white">
                <Link href="#como-funciona">Ver como funciona <ChevronRight aria-hidden="true" /></Link>
              </Button>
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-[13px] text-white/54" aria-label="Características principais">
              {["Fontes selecionáveis", "Dados por workspace", "Histórico organizado"].map((item) => (
                <li key={item} className="flex items-center gap-2"><Check className="size-3.5 text-signal-cyan" aria-hidden="true" />{item}</li>
              ))}
            </ul>
          </div>
          <div className="relative z-10 lg:pl-3"><SignalPreview /></div>
        </section>

        <section id="produto" className="border-y border-white/8 bg-white/[0.018]">
          <div className="mx-auto grid max-w-[1440px] divide-y divide-white/8 px-5 sm:grid-cols-3 sm:divide-x sm:divide-y-0 sm:px-8">
            {[
              [MapPinned, "Busca direcionada", "Nicho, cidade, região e fontes"],
              [ContactRound, "Ficha centralizada", "Dados e origem de cada lead"],
              [Workflow, "Pipeline integrado", "Etapas, atividades e follow-ups"],
            ].map(([Icon, title, copy]) => {
              const FeatureIcon = Icon as typeof MapPinned
              return (
                <div key={title as string} className="flex items-center gap-4 py-6 sm:px-7 first:sm:pl-0 last:sm:pr-0">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary"><FeatureIcon className="size-4.5" strokeWidth={1.75} aria-hidden="true" /></span>
                  <p><strong className="block text-sm font-semibold text-white">{title as string}</strong><span className="mt-1 block text-[12px] text-white/46">{copy as string}</span></p>
                </div>
              )
            })}
          </div>
        </section>

        <section id="como-funciona" className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 sm:py-28">
          <div className="mx-auto max-w-2xl text-center">
            <p className="eyebrow">Da busca ao acompanhamento</p>
            <h2 className="mt-4 text-balance text-4xl font-semibold leading-[1.05] tracking-[-0.045em] text-white sm:text-5xl">Um fluxo simples para não perder oportunidades.</h2>
            <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-white/54">Tudo começa com uma pesquisa e continua em uma rotina comercial clara, sem espalhar informações em várias ferramentas.</p>
          </div>
          <ol className="marketing-steps relative mt-14 grid gap-4 lg:grid-cols-3">
            {steps.map((step, index) => (
              <li key={step.number} className="marketing-step-card group relative overflow-hidden rounded-[22px] border border-white/10 bg-[var(--surface-1)] p-7">
                <span className="marketing-step-number">{step.number}</span>
                <span className="mt-16 grid size-11 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
                  {index === 0 ? <Search className="size-5" /> : index === 1 ? <ContactRound className="size-5" /> : <Workflow className="size-5" />}
                </span>
                <h3 className="mt-5 text-xl font-semibold tracking-[-0.025em] text-white">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-white/52">{step.copy}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="recursos" className="relative border-y border-white/8 bg-white/[0.018]">
          <div className="marketing-dot-field pointer-events-none absolute -right-40 top-0 size-[600px] opacity-35" aria-hidden="true" />
          <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 sm:py-28">
            <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
              <div><p className="eyebrow">O que você usa na prática</p><h2 className="mt-4 max-w-2xl text-4xl font-semibold tracking-[-0.045em] text-white sm:text-5xl">Cada etapa no lugar certo.</h2></div>
              <p className="max-w-md text-sm leading-6 text-white/50">Uma interface para pesquisar, revisar e acompanhar — construída ao redor do trabalho comercial real.</p>
            </div>
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {productCuts.map(({ icon: Icon, overline, title, copy }, index) => (
                <article key={overline} className="marketing-feature-card group rounded-[22px] border border-white/10 bg-[var(--surface-1)] p-7">
                  <div className="flex items-center justify-between"><span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="size-5" strokeWidth={1.75} aria-hidden="true" /></span><span className="font-mono text-[10px] text-white/28">0{index + 1}</span></div>
                  <p className="mt-10 text-[10px] font-semibold tracking-[0.16em] text-primary uppercase">{overline}</p>
                  <h3 className="mt-2 text-xl font-semibold tracking-[-0.025em] text-white">{title}</h3>
                  <p className="mt-3 text-sm leading-6 text-white/52">{copy}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 sm:py-28">
          <div className="marketing-cta relative overflow-hidden rounded-[28px] border border-primary/22 p-8 sm:p-12 lg:flex lg:items-center lg:justify-between lg:gap-10">
            <div className="marketing-cta-glow" aria-hidden="true" />
            <div className="relative"><p className="eyebrow">Sua operação começa aqui</p><h2 className="mt-3 max-w-2xl text-balance text-3xl font-semibold tracking-[-0.04em] text-white sm:text-5xl">Encontre. Organize. Avance.</h2><p className="mt-4 max-w-2xl text-sm leading-6 text-white/54">Crie sua conta, configure o workspace e faça sua primeira pesquisa no Hunter.</p></div>
            <Button asChild size="lg" className="relative mt-8 h-12 shrink-0 rounded-xl px-7 lg:mt-0"><Link href="/sign-up">Criar minha conta <ArrowRight aria-hidden="true" /></Link></Button>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/8">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-5 px-5 py-8 text-xs text-white/40 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <KiaraBrand inverse />
          <div className="flex flex-wrap items-center gap-4"><span className="flex items-center gap-1.5"><ShieldCheck className="size-3.5" />Dados organizados por workspace</span><span className="hidden size-1 rounded-full bg-white/20 sm:block" /><span>© 2026 Kiara Lead Intelligence</span></div>
        </div>
      </footer>
    </div>
  )
}
