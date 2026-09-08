import { SignUp } from "@clerk/nextjs"

export default function SignUpPage() {
  return <main className="grid min-h-screen place-items-center bg-slate-950 px-6 py-16 text-white"><section className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-cyan-950/30 backdrop-blur"><p className="mb-2 text-sm font-semibold tracking-[0.24em] text-cyan-300">KIARA</p><h1 className="text-3xl font-semibold tracking-tight">Crie sua conta</h1><p className="mb-8 mt-3 text-sm leading-6 text-slate-300">Depois do cadastro, crie ou selecione a organização que será seu workspace.</p><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" forceRedirectUrl="/onboarding" /></section></main>
}
