import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form"

export default function ForgotPasswordPage() {
  return <PremiumAuthShell eyebrow="Acesso protegido" title="Volte para sua operação." description="Recupere sua conta por e-mail com um link de uso único."><ForgotPasswordForm /></PremiumAuthShell>
}
