"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { LoaderCircle, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { createClient } from "@/lib/supabase/browser"

/** Ends the Kiara session on this device and returns to the sign-in page. */
export function LogoutButton({ className }: { className?: string }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function logout() {
    setBusy(true); setError("")
    try {
      const { error: signOutError } = await createClient().auth.signOut({ scope: "local" })
      if (signOutError) throw signOutError
      router.replace("/sign-in")
      router.refresh()
    } catch {
      setBusy(false)
      setError("Não foi possível sair agora. Tente novamente.")
    }
  }

  return <div className={className}>
    <Button type="button" variant="outline" onClick={() => void logout()} disabled={busy} className="text-destructive hover:text-destructive">
      {busy ? <LoaderCircle className="animate-spin" /> : <LogOut />}{busy ? "Saindo…" : "Sair da conta"}
    </Button>
    {error ? <p role="alert" className="mt-2 text-xs text-destructive">{error}</p> : null}
  </div>
}
