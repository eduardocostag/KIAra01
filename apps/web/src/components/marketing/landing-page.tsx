import Link from "next/link"
import Image from "next/image"
import { ArrowRight, Check, Hand, LayoutGrid, MessageCircle, ScanLine, Search, SlidersHorizontal, Smartphone, UserCheck } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { CtaOrb, HeroScene, MobileStickyCta, Reveal, SwipeRail, TiltCard, WordRotator } from "./landing-interactive"
import { LeadsPreview, PipelinePreview, PresencialPreview, WhatsAppPreview } from "./module-previews"
import styles from "./landing.module.css"

const channels = ["Google Maps", "Instagram", "Facebook", "Sites das empresas", "Receita Federal", "Cartão de visita", "Crachá de evento", "WhatsApp", "CRM com funil", "Follow-ups"]

const modules = [
  { icon: Search, tone: "#38bdf8", eyebrow: "Caça de leads", title: "Encontre clientes na internet.", copy: "Diga o nicho e as cidades. A Kiara pesquisa no Google Maps, nas redes e nos sites, confere telefone e endereço e entrega leads prontos para abordar.", bullets: ["Várias cidades numa busca, sem repetir empresas", "Celular e WhatsApp primeiro, com fonte conferida", "Responsável pela empresa pela Receita Federal"], preview: LeadsPreview },
  { icon: ScanLine, tone: "#f472b6", eyebrow: "Presencial", title: "Cartão de visita vira venda.", copy: "Numa feira, visita ou reunião, fotografe o cartão ou o crachá. A Kiara lê os dados, encontra a empresa e prepara a primeira mensagem citando o encontro.", bullets: ["Leitura do cartão em segundos", "Empresa, CNPJ e sócios encontrados sozinhos", "Mensagem pronta no seu WhatsApp com um toque"], preview: PresencialPreview },
  { icon: LayoutGrid, tone: "#facc15", eyebrow: "CRM", title: "Nenhum lead esquecido.", copy: "Todo contato entra no funil com a próxima ação. A fila de hoje mostra quem abordar, quem acompanhar e quais negociações estão paradas.", bullets: ["Funil com etapas e prioridade de cada lead", "Follow-ups no dia certo", "Resultados e ranking da equipe"], preview: PipelinePreview },
  { icon: MessageCircle, tone: "#34d399", eyebrow: "WhatsApp", title: "A Kiara continua a conversa.", copy: "Quando o cliente responde, a Kiara entende a conversa, qualifica, responde e chama você na hora certa, com limites e horários que você define.", bullets: ["Qualificação e próxima ação de cada contato", "Respostas no tom da sua empresa", "Você assume quando a venda esquenta"], preview: WhatsAppPreview },
]

const demo = [
  ["Fotografe o cartão", "Ou o crachá do evento. A Kiara lê nome, cargo, empresa, telefones, e-mail e redes."],
  ["Confira em segundos", "Celular com WhatsApp primeiro, empresa e sócios da Receita Federal já preenchidos."],
  ["Envie a mensagem pronta", "A Kiara escreve citando onde vocês se conheceram. Um toque abre o seu WhatsApp."],
  ["Acompanhe no CRM", "O contato entra no funil com follow-up agendado. Quando ele responde, a Kiara continua."],
]

const steps = [
  ["Encontre.", "Busque por nicho e cidade, ou fotografe o cartão de quem você conheceu."],
  ["Converse.", "A Kiara escreve a mensagem certa e atende quem responde no WhatsApp."],
  ["Venda.", "O CRM organiza o funil, os follow-ups e as prioridades do dia."],
]

const control = [
  { icon: Hand, label: "Você aprova cada abordagem" },
  { icon: Smartphone, label: "Mensagens saem do seu WhatsApp" },
  { icon: SlidersHorizontal, label: "Limites e horários" },
  { icon: UserCheck, label: "Dados de fontes públicas" },
]

const segments = ["agências", "imobiliárias", "representantes", "distribuidoras", "consultorias", "clínicas", "indústrias"]

const questions = [
  ["Preciso instalar alguma coisa?", "Não. A Kiara funciona no navegador do computador e do celular. O WhatsApp conecta por QR Code ou pela API oficial da Meta."],
  ["De onde vêm os dados dos leads?", "De fontes públicas: Google Maps, sites das empresas, redes sociais e Receita Federal. Cada lead mostra de onde veio cada informação."],
  ["Como funciona o Presencial?", "Você fotografa o cartão de visita ou o crachá. A Kiara lê os dados, encontra a empresa, salva no CRM e escreve a primeira mensagem. Você revisa e envia do seu WhatsApp."],
  ["A Kiara envia mensagens sozinha?", "A primeira mensagem sai sempre do seu WhatsApp, com a sua revisão. Depois que o cliente responde, a Kiara só responde sozinha se você ativar, dentro dos horários e limites que definir."],
]

export function LandingPage() {
  return (
    <div className="marketing-shell min-h-svh overflow-hidden bg-background text-foreground">
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>
      <div className="marketing-backdrop-effects" aria-hidden="true"><i className="backdrop-orbit orbit-a" /><i className="backdrop-orbit orbit-b" /><i className="backdrop-glow glow-a" /><i className="backdrop-glow glow-b" /></div>
      <header className="marketing-header sticky top-0 z-40 border-b border-white/8 bg-[#0d0c16]/78 backdrop-blur-2xl">
        <nav aria-label="Navegação principal" className="mx-auto flex h-[70px] max-w-[1320px] items-center gap-6 px-5 sm:px-8">
          <Link href="/" className="rounded-xl focus-visible:outline-offset-4" aria-label="Kiara, início"><KiaraBrand inverse /></Link>
          <div className="ml-auto hidden items-center gap-7 md:flex">
            <Link href="#modulos" className="marketing-nav-link">Plataforma</Link><Link href="#demonstracao" className="marketing-nav-link">Demonstração</Link><Link href="#como-funciona" className="marketing-nav-link">Como funciona</Link><Link href="#duvidas" className="marketing-nav-link">Dúvidas</Link>
          </div>
          <div className="ml-auto flex items-center gap-1.5 md:ml-3">
            <Button asChild variant="ghost" className="h-10 px-3 text-white/72 hover:bg-white/8 hover:text-white"><Link href="/sign-in">Entrar</Link></Button>
            <Button asChild className="h-10 rounded-[10px] px-4 shadow-[0_8px_28px_rgb(111_76_255/.18)]"><Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link></Button>
          </div>
        </nav>
      </header>

      <main id="conteudo">
        <section className="marketing-reference-hero relative mx-auto grid max-w-[1440px] items-center gap-10 overflow-hidden gap-y-2 px-5 pb-12 pt-6 sm:px-8 sm:pt-16 md:gap-y-10 lg:grid-cols-[.9fr_1.1fr] lg:pb-20">
          <Image src="/images/kiara-hero-ai.png" alt="" fill priority sizes="100vw" className="marketing-hero-art" />
          <div className="marketing-hero-shade" aria-hidden="true" />
          <div className="relative z-10 max-w-[560px]">
            <p className="eyebrow marketing-hero-eyebrow"><span className="marketing-live-dot" aria-hidden="true" /><span className="hidden md:inline">Prospecção, captação e CRM com IA</span><span className="md:hidden">Leads · captação · CRM</span></p>
            <h1 className="hero-display mt-5 text-balance text-white">A IA que encontra clientes e <span className="marketing-hero-accent">transforma em vendas.</span></h1>
            <p className="mt-6 max-w-[520px] text-pretty text-base leading-7 text-white/60">A Kiara busca leads na internet, transforma o cartão de quem você conheceu em contato no CRM, escreve a abordagem e acompanha cada negociação no WhatsApp até a venda.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row"><Button asChild size="lg" className="marketing-shine h-12 rounded-xl px-6 shadow-[0_16px_45px_rgb(91_54_199/.3)]"><Link href="/sign-up">Começar agora <ArrowRight aria-hidden="true" /></Link></Button><Button asChild size="lg" variant="outline" className="h-12 rounded-xl border-white/12 bg-white/[.025] px-6 text-white hover:bg-white/7 hover:text-white"><Link href="#modulos">Conhecer a plataforma</Link></Button></div>
            <div className="mt-7 grid max-w-[460px] grid-cols-2 gap-x-5 gap-y-2 text-xs text-white/50">{["Leads com fonte conferida", "Cartão de visita vira lead", "CRM com funil e follow-ups", "Atendimento no WhatsApp"].map((item) => <span key={item} className="flex items-center gap-1.5"><Check className="size-3.5 text-primary" />{item}</span>)}</div>
          </div>
          <div className="relative z-10 order-first md:order-none"><HeroScene /></div>
        </section>

        <div className="border-y border-white/8 bg-white/[.015] py-5"><div className={styles.marquee}><div className={styles.marqueeTrack}>{[...channels, ...channels].map((item, index) => <span key={`${item}-${index}`} aria-hidden={index >= channels.length}>{item}</span>)}</div></div></div>

        <section id="modulos" className="mx-auto max-w-[1320px] px-5 pb-4 pt-14 sm:px-8 sm:py-24">
          <Reveal className="mx-auto max-w-2xl text-center"><p className="eyebrow">Do primeiro contato à venda</p><h2 className="mt-3 text-balance text-4xl font-semibold leading-[1.05] tracking-[-.045em] text-white sm:text-5xl">Todo cliente, de qualquer lugar, no mesmo funil.</h2><p className="mt-4 text-sm leading-6 text-white/50 sm:text-base">Leads da internet e contatos feitos pessoalmente chegam ao mesmo CRM, com a mesma inteligência cuidando de cada conversa.</p><p className="mt-3 text-xs font-medium text-primary md:hidden">Deslize para ver tudo →</p></Reveal>
          <div className="mt-9 sm:mt-12"><SwipeRail labels={modules.map((module) => module.eyebrow)}>{modules.map(({ icon: Icon, tone, eyebrow, title, copy, bullets, preview: Preview }, index) => <Reveal key={eyebrow} delay={(index % 2) * 120} className="h-full">
            <TiltCard>
              <Preview />
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.14em]" style={{ color: tone }}><Icon className="size-4" aria-hidden="true" />{eyebrow}</p>
              <h3 className="mt-3 text-2xl font-semibold tracking-[-.03em] text-white">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-white/52">{copy}</p>
              <ul className="mt-4 space-y-2">{bullets.map((item) => <li key={item} className="flex items-start gap-2 text-sm text-white/72"><Check className="mt-0.5 size-4 shrink-0" style={{ color: tone }} />{item}</li>)}</ul>
            </TiltCard>
          </Reveal>)}</SwipeRail></div>
        </section>

        <section id="demonstracao" className="mx-auto max-w-[1100px] px-5 py-14 sm:px-8 sm:py-24">
          <Reveal className="mx-auto mb-10 max-w-2xl text-center sm:mb-14"><p className="eyebrow">Veja funcionando</p><h2 className="mt-3 text-balance text-4xl font-semibold leading-[1.05] tracking-[-.045em] text-white sm:text-5xl">Conheceu alguém? Em 1 minuto vira conversa.</h2><p className="mt-4 text-sm leading-6 text-white/50 sm:text-base">O cartão que ia para a gaveta vira contato no CRM e mensagem no WhatsApp, ali mesmo na feira.</p></Reveal>
          <div className={styles.demo}>
            <Reveal><div className={styles.phone}><video poster="/videos/kiara-presencial-demo.jpg" autoPlay muted loop playsInline preload="metadata" aria-label="Demonstração: um cartão de visita fotografado vira contato no CRM e mensagem pronta no WhatsApp"><source src="/videos/kiara-presencial-demo.webm" type="video/webm" /><source src="/videos/kiara-presencial-demo.mp4" type="video/mp4" /></video></div><p className="mt-3 text-center text-xs text-white/35">Demonstração com dados fictícios</p></Reveal>
            <Reveal delay={150}><ol className={styles.demoSteps}>{demo.map(([title, copy], index) => <li key={title} className={styles.demoStep}><b>{index + 1}</b><div><h3>{title}</h3><p>{copy}</p></div></li>)}</ol>
              <Button asChild size="lg" className="mt-8 h-12 rounded-xl px-6"><Link href="/sign-up">Quero testar <ArrowRight aria-hidden="true" /></Link></Button></Reveal>
          </div>
        </section>

        <section id="como-funciona" className="mx-auto max-w-[1100px] px-5 py-14 sm:px-8 sm:py-28">
          <Reveal className="relative">
            <p className="eyebrow mb-7 md:hidden">Como funciona</p>
            <div className={styles.timeline}>
              <span className={styles.timelineTrack} aria-hidden="true"><span className={styles.timelineFill} /></span>
              {steps.map(([title, copy], index) => <div key={title} className={styles.timelineStep}><span className={styles.timelineDot}>{index + 1}</span><h3>{title}</h3><p>{copy}</p></div>)}
            </div>
          </Reveal>
        </section>

        <section className="border-y border-white/8 bg-white/[.015] px-5 py-14 text-center sm:px-8 sm:py-28">
          <Reveal><h2 className={`${styles.statement} text-white`}>Você aprova.<br /><span>A Kiara executa.</span></h2></Reveal>
          <Reveal delay={150} className="mt-8 sm:mt-10"><div className={styles.chips}>{control.map(({ icon: Icon, label }) => <span key={label} className={styles.chip}><Icon aria-hidden="true" />{label}</span>)}</div></Reveal>
        </section>

        <section id="segmentos" className="px-5 py-14 text-center sm:px-8 sm:py-28">
          <Reveal><h2 className="text-balance text-4xl font-semibold tracking-[-.045em] text-white sm:text-6xl">Feita para <WordRotator words={segments} /></h2><p className="mx-auto mt-5 max-w-md text-sm leading-6 text-white/45 sm:text-base">A mesma Kiara, ajustada à sua oferta e ao seu público.</p></Reveal>
        </section>

        <section id="duvidas" className="mx-auto max-w-[760px] px-5 pb-14 sm:px-8 sm:pb-28">
          <Reveal><h2 className="mb-6 text-center text-2xl font-semibold tracking-[-.03em] text-white">Dúvidas frequentes</h2><div className={styles.faq}>{questions.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div></Reveal>
        </section>

        <section id="cta-final" className={styles.cta}>
          <Reveal className="relative">
            <CtaOrb />
            <h2 className="mx-auto max-w-2xl text-balance text-4xl font-semibold tracking-[-.045em] text-white sm:text-6xl">Coloque a Kiara para vender com você.</h2>
            <Button asChild size="lg" className="mt-9 h-12 rounded-xl px-7 shadow-[0_16px_45px_rgb(91_54_199/.35)]"><Link href="/sign-up">Criar minha conta <ArrowRight /></Link></Button>
          </Reveal>
        </section>
      </main>

      <MobileStickyCta>
        <span className="min-w-0 flex-1 text-[13px] leading-tight text-white/75"><strong className="block text-sm text-white">Teste a Kiara</strong>Comece em poucos minutos</span>
        <Button asChild className="marketing-shine h-11 shrink-0 rounded-xl px-4"><Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link></Button>
      </MobileStickyCta>

      <footer className="border-t border-white/8"><div className="mx-auto flex max-w-[1320px] items-center gap-4 px-5 pb-24 pt-6 md:py-6 text-xs text-white/35 sm:px-8"><KiaraBrand inverse /><Link href="/sign-in" className="-my-2 ml-auto px-2 py-2 hover:text-white">Entrar</Link></div></footer>
    </div>
  )
}
