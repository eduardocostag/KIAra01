"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { FormEvent, useState } from "react"
import { ArrowRight, LoaderCircle, LockKeyhole, Mail } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createClient } from "@/lib/supabase/browser"

export function SupabaseSignInForm() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const supabase = createClient()
      const result = await supabase.auth.signInWithPassword({ email: email.trim(), password })
      if (result.error) throw result.error
      router.replace("/app")
      router.refresh()
    } catch {
      setError("E-mail ou senha inválidos. Confira os dados liberados para sua conta.")
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="relative overflow-hidden rounded-[24px] border border-white/10 bg-[#15131d] p-6 text-white shadow-[0_28px_90px_rgb(0_0_0/.32)] sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-primary/20 blur-3xl" aria-hidden="true" />
      <div className="relative space-y-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-violet-300">Acesso seguro</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-.025em]">Entre na sua operação</h2>
          <p className="mt-2 text-sm leading-6 text-white/58">Use o e-mail e a senha vinculados ao seu workspace.</p>
        </div>

        {error ? <Alert variant="destructive"><LockKeyhole /><AlertTitle>Não foi possível entrar</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}

        <div className="grid gap-2">
          <Label htmlFor="email">E-mail</Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-3.5 size-4 text-white/40" aria-hidden="true" />
            <Input id="email" name="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} className="h-12 border-white/10 bg-black/20 pl-10 text-white" placeholder="voce@empresa.com" disabled={busy} />
          </div>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="password">Senha</Label>
          <div className="relative">
            <LockKeyhole className="pointer-events-none absolute left-3 top-3.5 size-4 text-white/40" aria-hidden="true" />
            <Input id="password" name="password" type="password" autoComplete="current-password" required minLength={6} value={password} onChange={(event) => setPassword(event.target.value)} className="h-12 border-white/10 bg-black/20 pl-10 text-white" placeholder="Sua senha" disabled={busy} />
          </div>
        </div>

        <Button type="submit" size="lg" className="h-12 w-full" disabled={busy || !email.trim() || !password}>
          {busy ? <LoaderCircle className="animate-spin" /> : <ArrowRight />}
          {busy ? "Entrando…" : "Entrar"}
        </Button>

        <p className="text-center text-sm text-white/52">Ainda não possui acesso? <Link href="/sign-up" className="font-semibold text-white transition hover:text-violet-300">Solicitar conta</Link></p>
      </div>
    </form>
  )
}
