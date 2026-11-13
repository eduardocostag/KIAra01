"use client"

import Link from "next/link"
import { useSyncExternalStore } from "react"
import { ArrowLeft, ArrowRight, Lock, Sparkles } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { EARLY_ACCESS, LAUNCH_AT, type EarlyAccessModule } from "@/lib/early-access"

function subscribe(onTick: () => void) {
  const timer = setInterval(onTick, 1000)
  return () => clearInterval(timer)
}
const nowSeconds = () => Math.floor(Date.now() / 1000)
const serverNow = () => null

/** Seconds until launch, ticking every second (null while rendering on the server). */
export function useLaunchCountdown() {
  const now = useSyncExternalStore(subscribe, nowSeconds, serverNow)
  if (now === null) return null
  return Math.max(0, Math.floor(new Date(LAUNCH_AT).getTime() / 1000) - now)
}

export function splitCountdown(seconds: number) {
  return { days: Math.floor(seconds / 86400), hours: Math.floor(seconds / 3600) % 24, minutes: Math.floor(seconds / 60) % 60, seconds: seconds % 60 }
}

function Unit({ value, label, accent }: { value: number | null; label: string; accent: string }) {
  const text = value === null ? "--" : String(value).padStart(2, "0")
  return <div className="relative flex w-[4.6rem] flex-col items-center overflow-hidden rounded-2xl border border-white/10 bg-white/[.04] px-2 pb-2.5 pt-3 backdrop-blur-xl sm:w-28 sm:pt-4">
    <span className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-white/10" aria-hidden="true" />
    <span key={text} className="kiara-tick text-4xl font-semibold tabular-nums tracking-tight sm:text-6xl" style={{ textShadow: `0 0 28px ${accent}` }}>{text}</span>
    <span className="mt-1 text-[10px] font-medium uppercase tracking-[.22em] text-white/50 sm:text-xs">{label}</span>
  </div>
}

export function ComingSoon({ module }: { module: EarlyAccessModule }) {
  const info = EARLY_ACCESS[module]
  const left = useLaunchCountdown()
  const parts = left === null ? null : splitCountdown(left)
  const launch = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "long", timeZone: "America/Sao_Paulo" }).format(new Date(LAUNCH_AT))
  return <main className="relative isolate flex min-h-dvh flex-col items-center justify-center overflow-hidden bg-[#05040b] px-4 pb-16 pt-24 text-white sm:pt-16" style={{ ["--accent" as string]: info.accent }}>
    <style>{`
      @keyframes kiara-drift { 0%,100% { transform: translate(-10%, -6%) scale(1) } 50% { transform: translate(8%, 6%) scale(1.15) } }
      @keyframes kiara-orbit { to { transform: rotate(360deg) } }
      @keyframes kiara-rise { from { opacity: 0; transform: translateY(18px) } to { opacity: 1; transform: none } }
      @keyframes kiara-tick { from { opacity: .2; transform: translateY(-30%) scale(.92); filter: blur(4px) } to { opacity: 1; transform: none; filter: none } }
      @keyframes kiara-shine { from { transform: translateX(-120%) } to { transform: translateX(220%) } }
      @keyframes kiara-grid { to { background-position: 0 80px } }
      .kiara-tick { animation: kiara-tick .45s cubic-bezier(.2,.8,.2,1) }
      .kiara-rise { animation: kiara-rise .9s cubic-bezier(.2,.8,.2,1) both }
      @media (prefers-reduced-motion: reduce) { .kiara-motion, .kiara-tick, .kiara-rise { animation: none !important } }
    `}</style>
    <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
      <div className="kiara-motion absolute left-1/2 top-1/3 size-[46rem] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40 blur-[120px]" style={{ background: info.accent, animation: "kiara-drift 14s ease-in-out infinite" }} />
      <div className="kiara-motion absolute -left-40 bottom-0 size-[36rem] rounded-full bg-[#3b1d7a] opacity-50 blur-[120px]" style={{ animation: "kiara-drift 18s ease-in-out infinite reverse" }} />
      <div className="kiara-motion absolute inset-x-[-50%] bottom-[-10%] h-[55%] opacity-40 [mask-image:linear-gradient(to_bottom,transparent,black_40%,transparent)]"
        style={{ backgroundImage: "linear-gradient(rgb(170 130 255 / .18) 1px, transparent 1px), linear-gradient(90deg, rgb(170 130 255 / .18) 1px, transparent 1px)", backgroundSize: "80px 80px", transform: "perspective(600px) rotateX(62deg)", animation: "kiara-grid 3s linear infinite" }} />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_50%,rgb(0_0_0/.7)_100%)]" />
    </div>

    <Link href="/app" className="absolute left-4 top-4 inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/10 bg-black/40 px-3.5 text-sm text-white/70 backdrop-blur-xl transition hover:text-white sm:left-8 sm:top-6">
      <ArrowLeft className="size-4" aria-hidden="true" />Módulos
    </Link>

    <div className="relative mb-10 grid size-56 place-items-center sm:size-64" aria-hidden="true">
      <span className="kiara-motion absolute inset-0 rounded-full border border-dashed" style={{ borderColor: `${info.accent}66`, animation: "kiara-orbit 30s linear infinite" }} />
      <span className="kiara-motion absolute inset-6 rounded-full border" style={{ borderColor: `${info.accent}44`, animation: "kiara-orbit 18s linear infinite reverse" }}>
        <span className="absolute -top-1.5 left-1/2 size-3 rounded-full" style={{ background: info.accent, boxShadow: `0 0 18px ${info.accent}` }} />
      </span>
      <span className="kiara-motion absolute inset-0" style={{ animation: "kiara-orbit 11s linear infinite" }}>
        <span className="absolute bottom-6 left-3 size-2 rounded-full bg-white shadow-[0_0_14px_white]" />
      </span>
      <span className="absolute inset-12 rounded-full blur-2xl" style={{ background: `${info.accent}55` }} />
      <KiaraOrb size="lg" active />
      <span className="absolute -bottom-3 inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-black/60 px-3 py-1 text-xs font-medium text-white/80 backdrop-blur-xl">
        <Lock className="size-3" />Acesso antecipado
      </span>
    </div>

    <p className="kiara-rise text-xs font-bold uppercase tracking-[.34em] sm:text-sm" style={{ color: info.accent, textShadow: `0 0 22px ${info.accent}` }}>{info.name} · em breve</p>
    <h1 className="kiara-rise mt-4 max-w-3xl text-balance text-center text-4xl font-semibold tracking-tight sm:text-6xl" style={{ animationDelay: ".1s" }}>{info.headline}</h1>
    <p className="kiara-rise mt-4 max-w-xl text-pretty text-center text-base text-white/60 sm:text-lg" style={{ animationDelay: ".2s" }}>{info.pitch}</p>

    <section className="kiara-rise mt-10 flex flex-col items-center" style={{ animationDelay: ".3s" }} aria-label="Contagem regressiva para o lançamento">
      {left === 0
        ? <p className="rounded-2xl border border-white/10 bg-white/5 px-6 py-4 text-lg font-medium">Chegou a hora. A liberação acontece em instantes.</p>
        : <div className="flex gap-2 sm:gap-4" role="timer" aria-live="off">
          <Unit value={parts?.days ?? null} label="dias" accent={info.accent} />
          <Unit value={parts?.hours ?? null} label="horas" accent={info.accent} />
          <Unit value={parts?.minutes ?? null} label="min" accent={info.accent} />
          <Unit value={parts?.seconds ?? null} label="seg" accent={info.accent} />
        </div>}
      <p className="mt-4 text-sm text-white/45">Lançamento em {launch}</p>
    </section>

    <ul className="kiara-rise mt-10 flex max-w-3xl flex-wrap justify-center gap-3" style={{ animationDelay: ".45s" }} aria-label="O que vem por aí">
      {info.teasers.map((teaser) => <li key={teaser} className="relative overflow-hidden rounded-full border border-white/10 bg-white/[.04] px-4 py-2 text-sm text-white/80 backdrop-blur-xl">
        <span className="kiara-motion pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/15 to-transparent" style={{ animation: "kiara-shine 3.2s ease-in-out infinite" }} aria-hidden="true" />
        <Sparkles className="mr-2 inline size-3.5" style={{ color: info.accent }} aria-hidden="true" />{teaser}
      </li>)}
    </ul>

    <Link href="/app/leads" className="kiara-rise mt-12 inline-flex min-h-11 items-center gap-2 rounded-xl px-5 text-sm font-semibold text-black transition hover:brightness-110" style={{ background: info.accent, boxShadow: `0 18px 50px -12px ${info.accent}`, animationDelay: ".6s" }}>
      Enquanto isso, use o KIARA Leads<ArrowRight className="size-4" aria-hidden="true" />
    </Link>
  </main>
}
