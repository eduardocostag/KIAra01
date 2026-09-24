import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"
import { SupabaseSignInForm } from "@/components/auth/supabase-sign-in-form"
import { supabaseConfig } from "@/lib/supabase/config"

async function isGoogleEnabled() {
  try {
    const { url, publishableKey } = supabaseConfig()
    const response = await fetch(`${url}/auth/v1/settings`, {
      headers: { apikey: publishableKey },
      cache: "no-store",
    })
    if (!response.ok) return false
    const settings = await response.json() as { external?: { google?: boolean } }
    return Boolean(settings.external?.google)
  } catch {
    return false
  }
}

export default async function SignInPage() {
  const googleEnabled = await isGoogleEnabled()
  return <PremiumAuthShell eyebrow="Seu cockpit comercial" title="Clareza para encontrar, decidir e avançar." description="Acesse sua operação, retome a fila e transforme dados públicos em próximos movimentos reais."><SupabaseSignInForm googleEnabled={googleEnabled} /></PremiumAuthShell>
}
