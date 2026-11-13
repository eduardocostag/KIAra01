import Link from "next/link"
import Image from "next/image"
import { ArrowRight, Bot, Check, Hand, MessageCircle, Puzzle, Search, SlidersHorizontal, UserCheck, Workflow } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { CtaOrb, HeroScene, Reveal, TiltCard, WordRotator } from "./landing-interactive"
import { AutomationPreview, LeadsPreview, VoicePreview, WhatsAppPreview } from "./module-previews"
import styles from "./landing.module.css"

const channels = ["Google Maps", "Instagram", "Facebook", "WhatsApp", "LinkedIn", "Google Ads", "Meta Ads", "Google Agenda", "CRM integrado", "Voz em português", "Chatwoot"]

const modules = [
  { icon: Search, tone: "#38bdf8", eyebrow: "KIARA Leads", title: "Encontre e organize clientes.", copy: "Descreva quem você procura e a Kiara pesquisa, confere contato e localização e leva cada oportunidade para o CRM com a próxima ação.", bullets: ["Busca por nicho, região e presença digital", "Contato e endereço conferidos na fonte", "Pipeline com etapas e follow-ups"], preview: LeadsPreview },
  { icon: MessageCircle, tone: "#34d399", eyebrow: "KIARA WhatsApp", title: "Atenda e prospecte no WhatsApp.", copy: "Conecte por QR Code. A Kiara entende cada conversa, atualiza o CRM e responde os contatos que você autorizar.", bullets: ["Conexão por QR Code, sem extensão", "Resumo, etapa e próxima ação de cada contato", "Respostas e follow-up com limites e horários"], preview: WhatsAppPreview },
  { icon: Bot, tone: "#c4a1ff", eyebrow: "KIARA Chat", title: "Converse com a Kiara.", copy: "Um assistente completo para pensar, escrever e criar. No modo conversa, o orbe da Kiara escuta e responde em voz alta.", bullets: ["Modo conversa por voz em português", "Cria sites, dashboards e planos de tarefas", "Histórico das suas conversas"], preview: VoicePreview },
  { icon: Workflow, tone: "#facc15", eyebrow: "KIARA Automation", title: "Automatize sem programar.", copy: "Monte fluxos ligando blocos: agenda, mensagens, redes sociais, sites, computador e anúncios, com o custo das campanhas visível antes.", bullets: ["Editor visual de blocos ligados por linhas", "Instagram, Facebook, LinkedIn e Google", "Meta, Google e LinkedIn Ads com custo previsto"], preview: AutomationPreview },
]

const steps = [
  ["Conte.", "Seu serviço, seu público e sua região."],
  ["Conecte.", "WhatsApp por QR Code e os canais que quiser."],
  ["Deixe trabalhar.", "A Kiara busca, atende e automatiza."],
]

const control = [
  { icon: Hand, label: "Confirmação para ações sensíveis" },
  { icon: SlidersHorizontal, label: "Limites e horários" },
  { icon: UserCheck, label: "Só contatos autorizados" },
  { icon: Puzzle, label: "Módulos sob medida" },
]

const segments = ["clínicas", "agências", "lojas", "escolas", "consultorias", "indústrias", "autônomos"]

const questions = [
  ["Preciso instalar alguma coisa?", "Não para começar. Leads, CRM, Chat e Automation funcionam no navegador. O que age no seu WhatsApp ou computador roda pelo serviço da Kiara no seu computador ou servidor."],
  ["A Kiara envia mensagens sozinha?", "Só se você ativar, apenas para contatos autorizados, dentro dos horários e limites que você definir."],
  ["Como funcionam os custos dos anúncios?", "O orçamento é seu e é cobrado pela plataforma. A Kiara mostra o valor por dia e o total antes de criar a campanha."],
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
            <Link href="#modulos" className="marketing-nav-link">Plataforma</Link><Link href="#como-funciona" className="marketing-nav-link">Como funciona</Link><Link href="#duvidas" className="marketing-nav-link">Dúvidas</Link>
          </div>
          <div className="ml-auto flex items-center gap-1.5 md:ml-3">
            <Button asChild variant="ghost" className="h-10 px-3 text-white/72 hover:bg-white/8 hover:text-white"><Link href="/sign-in">Entrar</Link></Button>
            <Button asChild className="h-10 rounded-[10px] px-4 shadow-[0_8px_28px_rgb(111_76_255/.18)]"><Link href="/sign-up">Criar conta <ArrowRight aria-hidden="true" /></Link></Button>
          </div>
        </nav>
      </header>

      <main id="conteudo">
        <section className="marketing-reference-hero relative mx-auto grid max-w-[1440px] items-center gap-10 overflow-hidden px-5 pb-14 pt-12 sm:px-8 sm:pt-16 lg:grid-cols-[.9fr_1.1fr] lg:pb-20">
          <Image src="/images/kiara-hero-ai.png" alt="" fill priority sizes="100vw" className="marketing-hero-art" />
          <div className="marketing-hero-shade" aria-hidden="true" />
          <div className="relative z-10 max-w-[560px]">
            <p className="eyebrow">Inteligência comercial, atendimento e automação</p>
            <h1 className="hero-display mt-5 text-balance text-white">A IA que prospecta, atende e trabalha por você.</h1>
            <p className="mt-6 max-w-[520px] text-pretty text-base leading-7 text-white/60">A Kiara encontra clientes, conversa no WhatsApp, responde por voz e automatiza suas tarefas e campanhas, com você aprovando o que importa.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row"><Button asChild size="lg" className="h-12 rounded-xl px-6 shadow-[0_16px_45px_rgb(91_54_199/.3)]"><Link href="/sign-up">Começar agora <ArrowRight aria-hidden="true" /></Link></Button><Button asChild size="lg" variant="outline" className="h-12 rounded-xl border-white/12 bg-white/[.025] px-6 text-white hover:bg-white/7 hover:text-white"><Link href="#modulos">Conhecer a plataforma</Link></Button></div>
            <div className="mt-7 grid max-w-[460px] grid-cols-2 gap-x-5 gap-y-2 text-xs text-white/50">{["Leads com fonte conferida", "WhatsApp por QR Code", "Conversa por voz", "Fluxos de automação"].map((item) => <span key={item} className="flex items-center gap-1.5"><Check className="size-3.5 text-primary" />{item}</span>)}</div>
          </div>
          <div className="relative z-10"><HeroScene /></div>
        </section>

        <div className="border-y border-white/8 bg-white/[.015] py-5"><div className={styles.marquee}><div className={styles.marqueeTrack}>{[...channels, ...channels].map((item, index) => <span key={`${item}-${index}`} aria-hidden={index >= channels.length}>{item}</span>)}</div></div></div>

        <section id="modulos" className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 sm:py-24">
          <Reveal className="mx-auto max-w-2xl text-center"><p className="eyebrow">Uma plataforma completa</p><h2 className="mt-3 text-balance text-4xl font-semibold leading-[1.05] tracking-[-.045em] text-white sm:text-5xl">Quatro módulos. Uma Kiara.</h2><p className="mt-4 text-sm leading-6 text-white/50 sm:text-base">Comece pelo que você mais precisa. Os módulos compartilham o mesmo CRM e a mesma inteligência.</p></Reveal>
          <div className="mt-12 grid gap-5 md:grid-cols-2">{modules.map(({ icon: Icon, tone, eyebrow, title, copy, bullets, preview: Preview }, index) => <Reveal key={eyebrow} delay={(index % 2) * 120}>
            <TiltCard>
              <Preview />
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.14em]" style={{ color: tone }}><Icon className="size-4" aria-hidden="true" />{eyebrow}</p>
              <h3 className="mt-3 text-2xl font-semibold tracking-[-.03em] text-white">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-white/52">{copy}</p>
              <ul className="mt-4 space-y-2">{bullets.map((item) => <li key={item} className="flex items-start gap-2 text-sm text-white/72"><Check className="mt-0.5 size-4 shrink-0" style={{ color: tone }} />{item}</li>)}</ul>
            </TiltCard>
          </Reveal>)}</div>
        </section>

        <section id="como-funciona" className="mx-auto max-w-[1100px] px-5 py-20 sm:px-8 sm:py-28">
          <Reveal className="relative">
            <div className={styles.timeline}>
              <span className={styles.timelineTrack} aria-hidden="true"><span className={styles.timelineFill} /></span>
              {steps.map(([title, copy], index) => <div key={title} className={styles.timelineStep}><span className={styles.timelineDot}>{index + 1}</span><h3>{title}</h3><p>{copy}</p></div>)}
            </div>
          </Reveal>
        </section>

        <section className="border-y border-white/8 bg-white/[.015] px-5 py-20 text-center sm:px-8 sm:py-28">
          <Reveal><h2 className={`${styles.statement} text-white`}>Você aprova.<br /><span>A Kiara executa.</span></h2></Reveal>
          <Reveal delay={150} className="mt-10"><div className={styles.chips}>{control.map(({ icon: Icon, label }) => <span key={label} className={styles.chip}><Icon aria-hidden="true" />{label}</span>)}</div></Reveal>
        </section>

        <section id="segmentos" className="px-5 py-20 text-center sm:px-8 sm:py-28">
          <Reveal><h2 className="text-balance text-4xl font-semibold tracking-[-.045em] text-white sm:text-6xl">Feita para <WordRotator words={segments} /></h2><p className="mx-auto mt-5 max-w-md text-sm leading-6 text-white/45 sm:text-base">A mesma Kiara, ajustada à sua oferta e ao seu público.</p></Reveal>
        </section>

        <section id="duvidas" className="mx-auto max-w-[760px] px-5 pb-20 sm:px-8 sm:pb-28">
          <Reveal><h2 className="mb-6 text-center text-2xl font-semibold tracking-[-.03em] text-white">Dúvidas frequentes</h2><div className={styles.faq}>{questions.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div></Reveal>
        </section>

        <section className={styles.cta}>
          <Reveal className="relative">
            <CtaOrb />
            <h2 className="mx-auto max-w-2xl text-balance text-4xl font-semibold tracking-[-.045em] text-white sm:text-6xl">Coloque a Kiara para trabalhar.</h2>
            <Button asChild size="lg" className="mt-9 h-12 rounded-xl px-7 shadow-[0_16px_45px_rgb(91_54_199/.35)]"><Link href="/sign-up">Criar minha conta <ArrowRight /></Link></Button>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-white/8"><div className="mx-auto flex max-w-[1320px] items-center gap-4 px-5 py-6 text-xs text-white/35 sm:px-8"><KiaraBrand inverse /><Link href="/sign-in" className="ml-auto hover:text-white">Entrar</Link></div></footer>
    </div>
  )
}
