"use client"

import Link from "next/link"
import { FormEvent, useState } from "react"
import { ArrowLeft, LoaderCircle, Mail } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createClient } from "@/lib/supabase/browser"

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("")
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = email.trim().toLowerCase()
    if (normalized === "admin" || normalized === "admin@kiara.local") {
      setError("O acesso administrativo não possui caixa de e-mail. Solicite a redefinição ao suporte da Kiara.")
      return
    }
    setBusy(true)
    setError(null)
    const supabase = createClient()
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(normalized, {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
    })
    setBusy(false)
    if (resetError) {
      setError("Não foi possível enviar o link agora. Tente novamente em alguns minutos.")
      return
    }
    setSent(true)
  }

  return (
    <form onSubmit={submit} className="rounded-[24px] border border-white/10 bg-[#15131d] p-6 text-white shadow-[0_28px_90px_rgb(0_0_0/.32)] sm:p-8">
      <div className="space-y-5">
        <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-violet-300">Recuperar acesso</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.025em]">Redefina sua senha</h2><p className="mt-2 text-sm leading-6 text-white/58">Informe o e-mail da conta. Enviaremos um link seguro para você criar outra senha.</p></div>
        {sent ? <Alert><Mail /><AlertTitle>Confira seu e-mail</AlertTitle><AlertDescription>Se a conta estiver cadastrada, o link de recuperação chegará em instantes. Verifique também o spam.</AlertDescription></Alert> : null}
        {error ? <Alert variant="destructive"><AlertTitle>Não foi possível continuar</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
        {!sent ? <><div className="grid gap-2"><Label htmlFor="recovery-email">E-mail</Label><Input id="recovery-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} className="h-12 border-white/10 bg-black/20 text-white" placeholder="voce@empresa.com" disabled={busy} /></div><Button className="h-12 w-full" disabled={busy || !email.trim()}>{busy ? <LoaderCircle className="animate-spin" /> : <Mail />}{busy ? "Enviando…" : "Enviar link de recuperação"}</Button></> : null}
        <Button asChild variant="ghost" className="w-full text-white/65 hover:bg-white/[.06] hover:text-white"><Link href="/sign-in"><ArrowLeft />Voltar para o login</Link></Button>
      </div>
    </form>
  )
}
