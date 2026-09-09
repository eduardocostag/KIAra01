"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"
import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

export function RefreshWorkspace() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  return <Button variant="outline" disabled={pending} onClick={() => startTransition(() => router.refresh())}>
    <RefreshCw className={pending ? "animate-spin motion-reduce:animate-none" : ""} />{pending ? "Atualizando…" : "Atualizar"}
  </Button>
}
