import { LockKeyhole, MessageCircle, Radar, ShieldCheck } from "lucide-react"
import { KSignal } from "@/components/brand/k-signal"
import { SignalTrail } from "@/components/brand/signal-trail"

export function SignalPreview() {
  return (
    <div className="hero-console relative" aria-label="Prévia ilustrativa do fluxo de uma conversa na Kiara">
      <div className="flex h-12 items-center justify-between border-b border-white/10 px-4 sm:px-5">
        <div className="flex items-center gap-2.5">
          <KSignal className="size-7 rounded-[9px] [&_svg]:size-5" />
          <span className="text-xs font-semibold tracking-[-0.01em] text-white">Inbox assistida</span>
        </div>
        <span className="rounded-full border border-amber-300/22 bg-amber-300/8 px-2.5 py-1 text-[10px] font-medium text-amber-200">
          Prévia demonstrativa
        </span>
      </div>

      <div className="grid sm:grid-cols-[156px_minmax(0,1fr)]">
        <aside className="hidden border-r border-white/8 p-3.5 sm:block" aria-label="Conversas ilustrativas">
          <p className="px-2 text-[10px] font-semibold tracking-[0.13em] text-white/48 uppercase">Recentes</p>
          <div className="mt-3 space-y-1.5">
            {[
              ["MC", "Nova DM", "agora"],
              ["RS", "Em revisão", "4 min"],
              ["AL", "Aguardando", "18 min"],
            ].map(([initials, state, time], index) => (
              <div
                key={initials}
                className={`relative flex items-center gap-2.5 rounded-[10px] px-2 py-2.5 ${index === 0 ? "bg-white/8 text-white" : "text-white/48"}`}
              >
                {index === 0 ? <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" /> : null}
                <span className="grid size-8 shrink-0 place-items-center rounded-full border border-white/10 bg-white/5 text-[10px] font-semibold">
                  {initials}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] font-medium">{state}</span>
                  <span className="mt-0.5 block font-mono text-[9px] text-white/40">{time}</span>
                </span>
              </div>
            ))}
          </div>
        </aside>

        <div className="min-w-0 p-4 sm:p-5">
          <SignalTrail compact completedThrough={1} className="mb-5" />

          <div className="space-y-3 border-y border-white/8 py-4">
            <div className="flex gap-3">
              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-white/7 text-white/62">
                <MessageCircle className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
              </span>
              <div className="rounded-xl rounded-tl-sm bg-white/7 px-3.5 py-3 text-xs leading-5 text-white/88">
                Oi! Queria conhecer os planos e saber se vocês atendem minha região.
              </div>
            </div>

            <div className="signal-edge rounded-xl border border-primary/18 p-3.5">
              <div className="flex items-center gap-2 text-[10px] font-semibold tracking-[0.12em] text-primary uppercase">
                <Radar className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
                Leitura da Kiara
              </div>
              <p className="mt-2 text-sm font-semibold tracking-[-0.018em] text-white">Interesse em preço identificado</p>
              <p className="mt-1 text-[11px] leading-5 text-white/58">
                Confirmado: busca por planos. Falta saber: região e prazo.
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-amber-300/16 bg-amber-300/6 p-3.5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 gap-2.5">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-amber-200" strokeWidth={1.75} aria-hidden="true" />
                <div>
                  <p className="text-xs font-semibold text-white">Resposta preparada</p>
                  <p className="mt-1 text-[10px] leading-4 text-white/50">Aguardando revisão humana. Nada foi enviado.</p>
                </div>
              </div>
              <span className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-white px-2.5 py-2 text-[10px] font-semibold text-[#171526]">
                <LockKeyhole className="size-3" aria-hidden="true" />
                Revisar
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
