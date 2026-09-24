import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"
import { SupabaseSignInForm } from "@/components/auth/supabase-sign-in-form"

export default function SignInPage() {
  return <PremiumAuthShell eyebrow="Seu cockpit comercial" title="Clareza para encontrar, decidir e avançar." description="Acesse sua operação, retome a fila e transforme dados públicos em próximos movimentos reais."><SupabaseSignInForm /></PremiumAuthShell>
}
