import type { ReactNode } from "react"
import { Layers3, ShieldCheck } from "lucide-react"
import { platformRoleLabels, type PlatformContext } from "@/lib/platform/contracts"
import { PlatformNav } from "./platform-nav"
import styles from "./platform.module.css"

export function PlatformShell({ context, children }: { context: PlatformContext; children: ReactNode }) {
  return <div className={styles.platform}>
    <header className={styles.identity}>
      <div className={styles.brand}><span aria-hidden="true"><Layers3 className="size-5" /></span><div><strong>KIARA</strong><p>Plataforma de operações</p></div></div>
      <div className={styles.account}><p>{context.organization.name}</p><span><ShieldCheck className="size-3.5" aria-hidden="true" />{platformRoleLabels[context.platform_role]}</span></div>
    </header>
    <PlatformNav modules={context.modules} />
    {children}
  </div>
}
