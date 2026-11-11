import Link from "next/link"
import { LockKeyhole, ServerOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import styles from "./platform.module.css"

export function PlatformUnavailable({ denied = false, requestId }: { denied?: boolean; requestId?: string | null }) {
  const Icon = denied ? LockKeyhole : ServerOff
  return <section className={styles.unavailable} aria-labelledby="platform-unavailable-title">
    <Icon className="size-7 text-muted-foreground" aria-hidden="true" />
    <h1 id="platform-unavailable-title">{denied ? "Acesso não disponível" : "Plataforma indisponível"}</h1>
    <p role="alert">{denied ? "Sua conta não tem acesso a este módulo. Consulte o administrador da sua empresa." : "Não foi possível confirmar os módulos da sua empresa no backend. Tente acessar novamente em instantes."}</p>
    {requestId ? <p className={styles.reference}>Referência: {requestId}</p> : null}
    <Button asChild variant="outline"><Link href="/app">Voltar ao início</Link></Button>
  </section>
}
