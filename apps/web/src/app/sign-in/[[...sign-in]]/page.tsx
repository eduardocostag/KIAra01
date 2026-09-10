import { SignIn } from "@clerk/nextjs"
import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"

export default function SignInPage() {
  return <PremiumAuthShell eyebrow="Seu cockpit comercial" title="Clareza para encontrar, decidir e avançar." description="Acesse sua operação, retome a fila e transforme dados públicos em próximos movimentos reais."><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" forceRedirectUrl="/onboarding" /></PremiumAuthShell>
}
