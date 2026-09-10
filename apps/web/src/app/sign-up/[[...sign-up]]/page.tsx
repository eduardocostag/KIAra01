import { SignUp } from "@clerk/nextjs"
import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"

export default function SignUpPage() {
  return <PremiumAuthShell eyebrow="Comece agora" title="Sua inteligência comercial, pronta no navegador." description="Crie seu acesso e configure um workspace seguro para leads, conversas, integrações e decisões."><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" forceRedirectUrl="/onboarding" /></PremiumAuthShell>
}
