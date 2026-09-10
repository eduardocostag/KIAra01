import type { ReactNode } from "react"
import Link from "next/link"
import { KiaraBrand } from "./kiara-brand"
import { KiaraOrb } from "./kiara-orb"

export function PremiumAuthShell({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children: ReactNode }) {
  return <main className="marketing-shell relative grid min-h-svh overflow-hidden lg:grid-cols-[1.05fr_.95fr]">
    <div className="marketing-dot-field pointer-events-none absolute -left-40 top-0 size-[760px] opacity-60" />
    <section className="relative hidden flex-col justify-between p-12 lg:flex xl:p-16"><Link href="/"><KiaraBrand inverse /></Link><div className="max-w-xl"><KiaraOrb size="lg" active /><p className="eyebrow mt-10">{eyebrow}</p><h1 className="kiara-editorial mt-4 text-5xl leading-[1.04] text-white xl:text-6xl">{title}</h1><p className="mt-6 max-w-lg text-base leading-7 text-white/60">{description}</p></div><p className="text-xs text-white/35">Kiara Lead Intelligence · Operação protegida</p></section>
    <section className="relative grid place-items-center border-l border-white/8 bg-white/[.025] px-5 py-12 backdrop-blur-xl"><div className="w-full max-w-md rounded-[30px] border border-white/10 bg-[#1d1a26]/90 p-6 shadow-[0_40px_120px_rgb(0_0_0/.45)] sm:p-8"><div className="mb-8 lg:hidden"><KiaraBrand inverse /></div>{children}</div></section>
  </main>
}
