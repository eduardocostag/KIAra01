"use client"

import Link from "next/link"
import { useState, type ReactNode } from "react"
import { ArrowLeft, Menu } from "lucide-react"
import { KiaraBrand } from "@/components/brand/kiara-brand"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"

/**
 * Full-height workspace with a single conversation-style sidebar, used by the
 * chat-like modules (KIARA Chat, WhatsApp). On small screens the sidebar moves
 * into a drawer opened from the top bar.
 */
export function ImmersiveShell({ label, sidebar, footer, topBar, children }: {
  label: string
  sidebar: (close: () => void) => ReactNode
  footer?: ReactNode
  topBar?: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const panel = (onNavigate: () => void) => <div className="flex h-full min-h-0 flex-col">
    <Link href="/app" onClick={onNavigate} className="mb-4 flex min-h-11 items-center px-2" aria-label="Kiara, início"><KiaraBrand inverse /></Link>
    <div className="min-h-0 flex-1 overflow-y-auto">{sidebar(onNavigate)}</div>
    <div className="mt-3 space-y-1 border-t border-sidebar-border pt-3">
      {footer}
      <Link href="/app" onClick={onNavigate} className="flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground"><ArrowLeft className="size-4" aria-hidden="true" />Trocar módulo</Link>
    </div>
  </div>

  return <div className="flex h-dvh min-h-0 w-full overflow-hidden">
    <aside aria-label={label} className="hidden w-[272px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-3 py-4 text-sidebar-foreground md:flex">{panel(() => {})}</aside>
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="left" className="w-[85vw] max-w-[300px] border-sidebar-border bg-sidebar p-3 text-sidebar-foreground">
        <SheetHeader className="sr-only"><SheetTitle>{label}</SheetTitle><SheetDescription>Navegação do módulo</SheetDescription></SheetHeader>
        {panel(close)}
      </SheetContent>
    </Sheet>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex min-h-14 shrink-0 items-center gap-2 border-b px-3 sm:px-4">
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Abrir menu" onClick={() => setOpen(true)}><Menu /></Button>
        <div className="flex min-w-0 flex-1 items-center gap-2">{topBar}</div>
      </header>
      <main id="conteudo" tabIndex={-1} className="flex min-h-0 flex-1 flex-col outline-none">{children}</main>
    </div>
  </div>
}
