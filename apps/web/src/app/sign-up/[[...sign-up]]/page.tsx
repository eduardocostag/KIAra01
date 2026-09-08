import { SignUp } from "@clerk/nextjs";
import { resolveAuthMode } from "@/lib/auth-config";

export default function SignUpPage() {
  const demo = resolveAuthMode() === "demo";
  return <main className="grid min-h-screen place-items-center bg-slate-950 px-6 py-16 text-white"><section className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-cyan-950/30 backdrop-blur"><p className="mb-2 text-sm font-semibold tracking-[0.24em] text-cyan-300">KIARA</p><h1 className="text-3xl font-semibold tracking-tight">Crie sua conta</h1><p className="mb-8 mt-3 text-sm leading-6 text-slate-300">Depois do cadastro, crie ou selecione a organização que será seu workspace.</p>{demo ? <div className="rounded-2xl border border-amber-300/40 bg-amber-300/10 p-5 text-sm text-amber-100"><strong className="block text-amber-300">Modo demonstração ativo</strong>Cadastro real está desativado enquanto as chaves Clerk não estiverem configuradas.</div> : <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" forceRedirectUrl="/app" />}</section></main>;
}
