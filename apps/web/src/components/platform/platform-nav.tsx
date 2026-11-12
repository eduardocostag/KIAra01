"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import type { PlatformModule } from "@/lib/platform/contracts"
import styles from "./platform.module.css"

export function PlatformNav({ modules }: { modules: readonly PlatformModule[] }) {
  const pathname = usePathname()
  return <nav aria-label="Módulos KIARA" className={styles.navigation}>
    <Link href="/app/platform" aria-current={pathname === "/app/platform" ? "page" : undefined}>Plataforma</Link>
    <Link href="/app/platform/skills" aria-current={pathname === "/app/platform/skills" ? "page" : undefined}>Skills</Link>
    {modules.map((module) => <Link key={module.key} href={module.key === "whatsapp" ? "/app/whatsapp" : ["atendimento", "intelligence"].includes(module.key) ? "/app/chat" : module.href}
      aria-current={pathname === module.href ? "page" : undefined}>{module.key === "atendimento" ? "Kiara Chat" : module.name}</Link>)}
  </nav>
}
