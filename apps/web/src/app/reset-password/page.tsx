import { PremiumAuthShell } from "@/components/brand/premium-auth-shell"
import { ResetPasswordForm } from "@/components/auth/reset-password-form"

export default function ResetPasswordPage() {
  return <PremiumAuthShell eyebrow="Acesso protegido" title="Escolha uma nova senha." description="Depois da alteração, entre novamente para continuar com segurança."><ResetPasswordForm /></PremiumAuthShell>
}
