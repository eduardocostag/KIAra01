import Link from "next/link"
import {
  ArrowRight,
  Check,
  ChevronRight,
  CircleDot,
  LockKeyhole,
  MessageCircle,
  Radar,
  ShieldCheck,
} from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { SignalTrail } from "@/components/brand/signal-trail"
import { Button } from "@/components/ui/button"
import { SignalPreview } from "./signal-preview"

const productCuts = [
  {
    icon: MessageCircle,
    overline: "Inbox",
    title: "Veja primeiro o que pede atenção.",
    copy: "Conversas novas, revisões e bloqueios ficam separados por estado — sem depender só de cor.",
  },
  {
    icon: Radar,
    overline: "Contexto",
    title: "Entenda antes de responder.",
    copy: "Fatos, inferências e o que ainda falta saber aparecem em camadas claramente identificadas.",
  },
  {
    icon: ShieldCheck,
    overline: "Pipeline",
    title: "Transforme conversa em próximo passo.",
    copy: "Cada oportunidade mantém motivo, responsável e ação recomendada no mesmo fluxo de trabalho.",
  },
]

export function LandingPage() {
  return (
    <div className="marketing-shell min-h-svh overflow-hidden bg-background text-foreground">
      <a href="#conteudo" className="skip-link">Pular para o conteúdo</a>

      <header className="sticky top-8 z-40 border-b border-white/8 bg-[#151421]/88 backdrop-blur-xl">
        <nav aria-label="Navegação principal" className="mx-auto flex h-[72px] max-w-[1440px] items-center gap-6 px-5 sm:px-8">
          <Link href="/" className="rounded-xl focus-visible:outline-offset-4" aria-label="Kiara Lead Intelligence, início">
            <KiaraBrand inverse />
          </Link>
          <div className="ml-auto hidden items-center gap-7 lg:flex">
            <Link href="#como-funciona" className="text-[13px] font-medium text-white/62 transition-colors hover:text-white">Como funciona</Link>
            <Link href="#controle" className="text-[13px] font-medium text-white/62 transition-colors hover:text-white">Controle humano</Link>
            <Link href="#seguranca" className="text-[13px] font-medium text-white/62 transition-colors hover:text-white">Segurança</Link>
          </div>
          <div className="ml-auto flex items-center gap-1.5 lg:ml-4">
            <Button asChild variant="ghost" className="h-11 px-3 text-white hover:bg-white/8 hover:text-white">
              <Link href="/sign-in">Entrar</Link>
            </Button>
            <Button asChild className="h-11 rounded-[11px] px-4 hover:bg-[var(--primary-hover)]">
              <Link href="/sign-up">Começar <ArrowRight aria-hidden="true" /></Link>
            </Button>
          </div>
        </nav>
      </header>

      <main id="conteudo">
        <section className="relative mx-auto grid max-w-[1440px] items-center gap-12 px-5 pb-20 pt-14 sm:px-8 sm:pt-20 lg:grid-cols-[0.92fr_1.08fr] lg:gap-14 lg:pb-24 lg:pt-20">
          <div className="marketing-dot-field pointer-events-none absolute -right-24 top-0 -z-10 size-[720px] opacity-80" aria-hidden="true" />
          <div className="relative z-10 max-w-[650px]">
            <p className="eyebrow">Instagram inbound → qualificação → pipeline</p>
            <h1 className="hero-display mt-6 text-balance text-white">Transforme cada DM em uma próxima ação.</h1>
            <p className="mt-7 max-w-[590px] text-pretty text-[17px] leading-7 tracking-[-0.012em] text-white/64 sm:text-lg sm:leading-8">
              A Kiara lê o contexto, mostra o que falta e prepara a resposta. Você revisa antes de qualquer envio.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="h-12 rounded-xl px-6 shadow-[0_0_0_5px_oklch(0.735_0.16_273/0.08)] hover:bg-[var(--primary-hover)]">
                <Link href="/sign-up">Criar workspace <ArrowRight aria-hidden="true" /></Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-12 rounded-xl border-white/14 bg-white/4 px-6 text-white hover:bg-white/9 hover:text-white">
                <Link href="#como-funciona">Conhecer o fluxo <ChevronRight aria-hidden="true" /></Link>
              </Button>
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-[13px] text-white/58" aria-label="Características principais">
              {["Sem instalação", "Aprovação humana", "Opt-out respeitado"].map((item) => (
                <li key={item} className="flex items-center gap-2"><Check className="size-3.5 text-signal-cyan" aria-hidden="true" />{item}</li>
              ))}
            </ul>
          </div>
          <div className="relative z-10 lg:pl-2"><SignalPreview /></div>
        </section>

        <section id="seguranca" className="border-y border-white/8 bg-white/[0.018]">
          <div className="mx-auto grid max-w-[1440px] divide-y divide-white/8 px-5 sm:grid-cols-3 sm:divide-x sm:divide-y-0 sm:px-8">
            {[
              ["Sem instalação", "Acesso direto pelo navegador"],
              ["Controle humano", "Aprovação antes de ações externas"],
              ["Canal responsável", "Integração desenhada para a API oficial"],
            ].map(([title, copy]) => (
              <div key={title} className="flex items-center gap-3 py-5 sm:px-6 first:sm:pl-0 last:sm:pr-0">
                <CircleDot className="size-4 shrink-0 text-signal-cyan" strokeWidth={1.75} aria-hidden="true" />
                <p><strong className="block text-xs font-semibold text-white">{title}</strong><span className="mt-0.5 block text-[11px] text-white/48">{copy}</span></p>
              </div>
            ))}
          </div>
        </section>

        <section id="como-funciona" className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 sm:py-28">
          <div className="grid gap-12 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20">
            <div>
              <p className="eyebrow">Da mensagem à decisão</p>
              <h2 className="mt-4 max-w-md text-4xl font-semibold leading-[1.06] tracking-[-0.045em] text-white">Um caminho curto, visível e governado.</h2>
              <p className="mt-5 max-w-md text-base leading-7 text-white/56">Cada etapa deixa claro o que a Kiara interpretou, o que depende de você e o que de fato aconteceu.</p>
            </div>
            <div className="rounded-[20px] border border-white/10 bg-white/[0.025] p-6 sm:p-8"><SignalTrail completedThrough={2} /></div>
          </div>

          <div className="mt-20 grid gap-4 lg:grid-cols-3">
            {productCuts.map(({ icon: Icon, overline, title, copy }, index) => (
              <article key={overline} className="group rounded-[18px] border border-white/10 bg-[var(--surface-1)] p-6 transition-[border-color,transform] duration-200 hover:-translate-y-px hover:border-primary/30">
                <div className="flex items-center justify-between"><Icon className="size-5 text-primary" strokeWidth={1.75} aria-hidden="true" /><span className="font-mono text-[10px] text-white/32">0{index + 1}</span></div>
                <p className="mt-9 text-[10px] font-semibold tracking-[0.14em] text-white/42 uppercase">{overline}</p>
                <h3 className="mt-2 text-lg font-semibold tracking-[-0.022em] text-white">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-white/54">{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="controle" className="border-y border-white/8 bg-white/[0.018]">
          <div className="mx-auto grid max-w-[1440px] items-center gap-12 px-5 py-20 sm:px-8 sm:py-24 lg:grid-cols-2 lg:gap-20">
            <div>
              <p className="eyebrow">Automação com limites claros</p>
              <h2 className="mt-4 text-4xl font-semibold tracking-[-0.045em] text-white">A velocidade nunca apaga a decisão.</h2>
              <p className="mt-5 max-w-xl text-base leading-7 text-white/56">A interface separa preparação, aprovação e resultado para que sua equipe saiba exatamente onde cada conversa está.</p>
            </div>
            <div className="rounded-[20px] border border-white/10 bg-[var(--surface-1)] p-5 sm:p-7">
              <div className="grid gap-3 sm:grid-cols-3">
                {["Preparado", "Aprovado", "Enviado"].map((state, index) => (
                  <div key={state} className={`rounded-xl border p-4 ${index === 1 ? "border-primary/28 bg-primary/9" : "border-white/8 bg-white/[0.025]"}`}>
                    <span className="font-mono text-[10px] text-white/38">0{index + 1}</span>
                    <strong className="mt-3 block text-sm text-white">{state}</strong>
                    <span className="mt-1 block text-[11px] leading-4 text-white/46">{index === 0 ? "Rascunho interno" : index === 1 ? "Decisão registrada" : "Confirmação do canal"}</span>
                  </div>
                ))}
              </div>
              <p className="mt-5 flex items-center gap-2 text-xs font-medium text-amber-200"><LockKeyhole className="size-4" aria-hidden="true" />Preparado ≠ Aprovado ≠ Enviado</p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 sm:py-28">
          <div className="flex flex-col items-start justify-between gap-8 rounded-[24px] border border-primary/22 bg-primary/10 p-7 sm:p-10 lg:flex-row lg:items-center">
            <div><p className="eyebrow">Kiara no navegador</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-white sm:text-4xl">Seu próximo atendimento começa com clareza.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-white/56">Crie seu workspace e prepare sua operação B2C para atender pelo Instagram.</p></div>
            <Button asChild size="lg" className="h-12 shrink-0 rounded-xl px-6 hover:bg-[var(--primary-hover)]"><Link href="/sign-up">Criar workspace <ArrowRight aria-hidden="true" /></Link></Button>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/8">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-4 px-5 py-8 text-xs text-white/42 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <KiaraBrand inverse />
          <span>© 2026 Kiara Lead Intelligence · Controle humano por padrão</span>
        </div>
      </footer>
    </div>
  )
}
