"use client"

import { FormEvent, useState } from "react"
import { useRouter } from "next/navigation"
import { Check, LoaderCircle, LockKeyhole } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createClient } from "@/lib/supabase/browser"

export function ResetPasswordForm() {
  const router = useRouter()
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (password.length < 8) return setError("Use pelo menos 8 caracteres na nova senha.")
    if (password !== confirmation) return setError("As senhas não coincidem.")
    setBusy(true)
    setError(null)
    const supabase = createClient()
    const { error: updateError } = await supabase.auth.updateUser({ password })
    if (updateError) {
      setBusy(false)
      setError("O link expirou ou já foi usado. Solicite uma nova recuperação de senha.")
      return
    }
    await supabase.auth.signOut({ scope: "local" })
    router.replace("/sign-in?password=updated")
    router.refresh()
  }

  return (
    <form onSubmit={submit} className="rounded-[24px] border border-white/10 bg-[#15131d] p-6 text-white shadow-[0_28px_90px_rgb(0_0_0/.32)] sm:p-8">
      <div className="space-y-5">
        <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-violet-300">Nova senha</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.025em]">Proteja sua conta</h2><p className="mt-2 text-sm leading-6 text-white/58">Crie uma senha com pelo menos 8 caracteres.</p></div>
        {error ? <Alert variant="destructive"><LockKeyhole /><AlertTitle>Não foi possível salvar</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
        <div className="grid gap-2"><Label htmlFor="new-password">Nova senha</Label><Input id="new-password" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} className="h-12 border-white/10 bg-black/20 text-white" disabled={busy} /></div>
        <div className="grid gap-2"><Label htmlFor="confirm-password">Confirmar senha</Label><Input id="confirm-password" type="password" autoComplete="new-password" minLength={8} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="h-12 border-white/10 bg-black/20 text-white" disabled={busy} /></div>
        <Button className="h-12 w-full" disabled={busy || !password || !confirmation}>{busy ? <LoaderCircle className="animate-spin" /> : <Check />}{busy ? "Salvando…" : "Salvar nova senha"}</Button>
      </div>
    </form>
  )
}
