import Link from "next/link"
import Image from "next/image"
import { ArrowRight, Check, ContactRound, Globe2, Workflow } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { ProductPreview } from "./product-preview"
import { SignalPreview } from "./signal-preview"

const features = [
  { icon: Globe2, eyebrow: "Hunter", title: "Busque por perfil e região.", copy: "Escolha as fontes, defina os critérios e acompanhe os resultados da pesquisa." },
  { icon: ContactRound, eyebrow: "Leads", title: "Revise tudo em uma ficha.", copy: "Origem, canais disponíveis, endereço e atividades ficam no mesmo contexto." },
  { icon: Workflow, eyebrow: "Pipeline", title: "Saiba sempre o próximo passo.", copy: "Organize etapas, registre contatos e mantenha follow-ups visíveis." },
]

const questions = [
  ["Que tipo de lead posso pesquisar?", "Você define profissão ou nicho, localidade, presença digital, contato necessário e as fontes da pesquisa."],
  ["Os dados de clientes ficam separados?", "Sim. Leads, pesquisas, histórico e configurações são organizados por workspace."],
  ["A Kiara envia mensagens automaticamente?", "Não. A Kiara prepara o contexto e abre o canal disponível; o envio continua sob seu controle."],
]

const segments = [
  ["Saúde", "Clínicas e consultórios"],
  ["Tecnologia", "Startups e empresas de TI"],
  ["Indústria", "Fabricantes e fornecedores"],
  ["Serviços", "Agências e consultorias"],
  ["Educação", "Escolas e cursos"],
  ["Varejo", "Lojas e e-commerces"],
]

export function LandingPage() {
  return (
    <div className="marketing-shell min-h-svh overflow-hidden bg-background text-foreground">
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>
      <div className="marketing-backdrop-effects" aria-hidden="true"><i className="backdrop-orbit orbit-a" /><i className="backdrop-orbit orbit-b" /><i className="backdrop-glow glow-a" /><i className="backdrop-glow glow-b" /></div>
      <header className="marketing-header sticky top-0 z-40 border-b border-white/8 bg-[#0d0c16]/78 backdrop-blur-2xl">
        <nav aria-label="Navegação principal" className="mx-auto flex h-[70px] max-w-[1320px] items-center gap-6 px-5 sm:px-8">
          <Link href="/" className="rounded-xl focus-visible:outline-offset-4" aria-label="Kiara Lead Intelligence, início"><KiaraBrand inverse /></Link>
          <div className="ml-auto hidden items-center gap-7 md:flex">
            <Link href="#produto" className="marketing-nav-link">Produto</Link><Link href="#segmentos" className="marketing-nav-link">Soluções</Link><Link href="#recursos" className="marketing-nav-link">Recursos</Link><Link href="#duvidas" className="marketing-nav-link">Dúvidas</Link>
          </div>
          <div className="ml-auto flex items-center gap-1.5 md:ml-3">
            <Button asChild variant="ghost" className="h-10 px-3 text-white/72 hover:bg-white/8 hover:text-white"><Link href="/sign-in">Entrar</Link></Button>
            <Button asChild className="h-10 rounded-[10px] px-4 shadow-[0_8px_28px_rgb(111_76_255/.18)]"><Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link></Button>
          </div>
        </nav>
      </header>

      <main id="conteudo">
        <section className="marketing-reference-hero relative mx-auto grid max-w-[1440px] items-center gap-12 overflow-hidden px-5 pb-16 pt-14 sm:px-8 sm:pt-20 lg:grid-cols-[.82fr_1.18fr] lg:pb-20">
          <Image src="/images/kiara-hero-ai.png" alt="" fill priority sizes="100vw" className="marketing-hero-art" />
          <div className="marketing-hero-shade" aria-hidden="true" />
          <div className="marketing-dot-field pointer-events-none absolute -right-48 top-0 z-[1] size-[680px] opacity-30" aria-hidden="true" />
          <div className="relative z-10 max-w-[535px]">
            <p className="eyebrow">Prospecção organizada, do início ao avanço</p><h1 className="hero-display mt-5 text-balance text-white">Encontre leads e avance com clareza.</h1>
            <p className="mt-6 max-w-[500px] text-pretty text-base leading-7 text-white/58">Pesquise oportunidades, revise os dados encontrados e conduza cada lead pelo Pipeline.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row"><Button asChild size="lg" className="h-12 rounded-xl px-6 shadow-[0_16px_45px_rgb(91_54_199/.22)]"><Link href="/sign-up">Começar agora <ArrowRight aria-hidden="true" /></Link></Button><Button asChild size="lg" variant="outline" className="h-12 rounded-xl border-white/12 bg-white/[.025] px-6 text-white hover:bg-white/7 hover:text-white"><Link href="#produto">Conhecer a Kiara</Link></Button></div>
            <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-white/42">{["Busca por localidade", "Dados centralizados", "Controle por workspace"].map((item) => <span key={item} className="flex items-center gap-1.5"><Check className="size-3 text-primary" />{item}</span>)}</div>
          </div>
          <div className="relative z-10"><SignalPreview /></div>
        </section>

        <section id="produto" className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 sm:py-20">
          <div><p className="eyebrow">Uma visão completa</p><h2 className="mt-3 max-w-lg text-balance text-4xl font-semibold leading-[1.05] tracking-[-.045em] text-white sm:text-5xl">Da pesquisa ao relacionamento.</h2></div>
          <div className="mt-9"><ProductPreview /></div>
        </section>

        <section id="segmentos" className="reference-segments border-y border-white/8 bg-white/[.016]">
          <div className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 sm:py-20">
            <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><p className="eyebrow">Soluções por segmento</p><h2 className="mt-4 max-w-md text-4xl font-semibold leading-[1.04] tracking-[-.045em] text-white">Prospecção para diferentes mercados.</h2></div><p className="max-w-md text-sm leading-6 text-white/46">Use filtros e fontes adequados ao público que sua empresa precisa encontrar.</p></div>
            <div className="segment-card-track mt-10">{segments.map(([title, copy], index) => <article className="segment-card" key={title}><div className={`segment-photo segment-${index}`}><Image src="/images/kiara-segments.png" alt={`Profissional do segmento de ${title}`} fill sizes="100vw" /></div><div className="segment-card-copy"><h3>{title}</h3><p>{copy}</p><Link href="/sign-up">Encontrar leads <ArrowRight /></Link></div></article>)}</div>
          </div>
        </section>

        <section id="recursos"><div className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 sm:py-20">
          <div className="max-w-xl"><p className="eyebrow">O essencial, bem resolvido</p><h2 className="mt-4 text-4xl font-semibold tracking-[-.045em] text-white">Três etapas. Um único fluxo.</h2></div>
          <div className="mt-10 grid gap-4 lg:grid-cols-3">{features.map(({ icon: Icon, eyebrow, title, copy }, index) => <article className="reference-feature-card" key={eyebrow}><div className="reference-feature-visual"><span className={`reference-orbit orbit-${index + 1}`} /><Icon /></div><p className="eyebrow mt-6">{eyebrow}</p><h3 className="mt-2 text-xl font-semibold tracking-[-.025em] text-white">{title}</h3><p className="mt-3 text-sm leading-6 text-white/48">{copy}</p></article>)}</div>
        </div></section>

        <section id="duvidas" className="mx-auto grid max-w-[1320px] gap-10 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[.72fr_1.28fr]">
          <div><p className="eyebrow">Dúvidas frequentes</p><h2 className="mt-4 max-w-sm text-4xl font-semibold tracking-[-.045em] text-white">Direto ao ponto.</h2><p className="mt-4 max-w-sm text-sm leading-6 text-white/46">O que você precisa saber antes de começar.</p></div>
          <div className="reference-faq">{questions.map(([question, answer], index) => <details key={question} open={index === 0}><summary>{question}<span>+</span></summary><p>{answer}</p></details>)}</div>
        </section>

        <section className="px-5 pb-14 sm:px-8 sm:pb-16"><div className="reference-final-cta mx-auto max-w-[1320px]"><div className="reference-cta-orb" aria-hidden="true" /><div className="relative"><p className="eyebrow">Comece com uma pesquisa</p><h2 className="mt-3 max-w-xl text-balance text-3xl font-semibold tracking-[-.04em] text-white sm:text-5xl">Transforme buscas em oportunidades organizadas.</h2></div><Button asChild size="lg" className="relative h-12 shrink-0 rounded-xl px-6"><Link href="/sign-up">Criar minha conta <ArrowRight /></Link></Button></div></section>
      </main>
    </div>
  )
}
