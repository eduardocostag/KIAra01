import Link from "next/link"
import { ArrowRight, Check, MessageCircle, ShieldCheck, Sparkles } from "lucide-react"
import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"

export default function SignUpPage() {
  const message = encodeURIComponent("Olá! Quero criar minha conta na Kiara e conhecer melhor a plataforma.")
  const whatsappUrl = `https://wa.me/5551995114237?text=${message}`

  return <PremiumAuthShell eyebrow="Acesso acompanhado" title="Comece com a Kiara do jeito certo." description="Antes de liberar seu workspace, entendemos sua operação e deixamos o ambiente preparado para você começar com clareza.">
    <div className="relative overflow-hidden rounded-[24px] border border-white/10 bg-[#15131d] p-6 text-white shadow-[0_28px_90px_rgb(0_0_0/.32)] sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-primary/20 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 size-48 rounded-full bg-violet-500/10 blur-3xl" aria-hidden="true" />

      <div className="relative">
        <div className="mb-6 flex items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-violet-200">
            <Sparkles className="size-3.5" aria-hidden="true" /> Acesso personalizado
          </span>
          <span className="flex items-center gap-2 text-xs text-white/45"><span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_14px_rgb(52_211_153/.75)]" />Atendimento direto</span>
        </div>

        <h2 className="text-balance text-3xl font-semibold tracking-[-.035em]">Vamos preparar seu acesso.</h2>
        <p className="mt-3 text-sm leading-6 text-white/58">Fale conosco pelo WhatsApp para conhecermos sua necessidade e liberarmos sua conta com a configuração inicial adequada.</p>

        <div className="my-7 grid gap-3 border-y border-white/8 py-6 text-sm text-white/72">
          {["Ativação acompanhada", "Workspace configurado para sua operação", "Contato direto para começar"].map((item) => <div key={item} className="flex items-center gap-3"><span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/14 text-violet-300"><Check className="size-3.5" aria-hidden="true" /></span>{item}</div>)}
        </div>

        <a href={whatsappUrl} target="_blank" rel="noreferrer" className="group flex min-h-14 w-full items-center justify-between rounded-xl bg-[#25d366] px-4 font-semibold text-[#07170d] shadow-[0_18px_45px_rgb(37_211_102/.18)] transition hover:-translate-y-0.5 hover:bg-[#2be070] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#65ef9c] focus-visible:ring-offset-2 focus-visible:ring-offset-[#15131d]">
          <span className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-black/10"><MessageCircle className="size-5" aria-hidden="true" /></span><span className="text-left"><span className="block">Solicitar acesso pelo WhatsApp</span><span className="block text-xs font-medium opacity-65">(51) 99511-4237</span></span></span>
          <ArrowRight className="size-5 transition-transform group-hover:translate-x-1" aria-hidden="true" />
        </a>

        <div className="mt-5 flex items-center justify-center gap-2 text-xs text-white/42"><ShieldCheck className="size-4" aria-hidden="true" />Seus dados de acesso continuam protegidos.</div>
        <p className="mt-7 text-center text-sm text-white/52">Já possui uma conta? <Link href="/sign-in" className="font-semibold text-white transition hover:text-violet-300">Entrar</Link></p>
      </div>
    </div>
  </PremiumAuthShell>
}
