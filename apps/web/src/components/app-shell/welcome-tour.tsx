"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, ArrowRight, KanbanSquare, MessageCircle, Search, Sparkles, Target } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"

const EXAMPLE = { q: "Clínicas odontológicas sem site", local: "Porto Alegre, RS" }
const hunterExample = (q: string, local: string) => `/app/hunter?${new URLSearchParams({ q, local })}`

/** Three short steps for someone new: what Kiara does, ready examples and where to start. Shown once per person and browser. */
export function WelcomeTour({ userId, fullAccess }: { userId: string; fullAccess: boolean }) {
  const key = `kiara-welcome:v1:${userId}`
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)

  useEffect(() => {
    let seen = true
    try { seen = localStorage.getItem(key) === "done" } catch { /* storage blocked: do not insist */ }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!seen) setOpen(true)
    const reopen = () => { setStep(0); setOpen(true) }
    window.addEventListener("kiara:welcome", reopen)
    return () => window.removeEventListener("kiara:welcome", reopen)
  }, [key])

  function close() {
    setOpen(false)
    try { localStorage.setItem(key, "done") } catch { /* optional */ }
  }

  const examples = [
    { icon: Search, title: "Encontrar clientes", text: "“Clínicas odontológicas sem site em Porto Alegre”: a Kiara busca, confere telefone e endereço e dá uma nota para cada lead.", href: hunterExample(EXAMPLE.q, EXAMPLE.local) },
    { icon: KanbanSquare, title: "Organizar o funil", text: "Os leads que você aprova entram no funil, do primeiro contato ao fechamento.", href: "/app/pipeline" },
    ...(fullAccess ? [{ icon: MessageCircle, title: "Perguntar à Kiara", text: "Converse, anexe uma planilha ou um contrato, peça uma imagem ou um vídeo curto.", href: "/app/chat" }] : []),
  ]
  const steps = [
    {
      title: "Boas-vindas à Kiara",
      description: "Sua assistente comercial: encontra empresas que combinam com o seu negócio, confere os contatos e ajuda a transformar leads em clientes.",
      body: <ul className="space-y-3">{[
        { icon: Target, text: "Você descreve quem procura, em palavras comuns." },
        { icon: Sparkles, text: "A Kiara pesquisa no Google Maps e na web, confere cada contato e explica por que o lead vale a pena." },
        { icon: KanbanSquare, text: "Você escolhe os melhores e acompanha tudo no funil." },
      ].map(({ icon: Icon, text }) => <li key={text} className="flex items-start gap-3 text-sm"><span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/15 text-primary"><Icon className="size-4" aria-hidden="true" /></span><span className="pt-1.5">{text}</span></li>)}</ul>,
    },
    {
      title: "Exemplos prontos",
      description: "Toque em um exemplo para ver como funciona. Nada é enviado a ninguém sem você aprovar.",
      body: <div className="grid gap-2">{examples.map(({ icon: Icon, title, text, href }) => <Link key={title} href={href} onClick={close} className="group flex items-start gap-3 rounded-2xl border p-3 transition-colors hover:border-primary/50 hover:bg-muted/40">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary"><Icon className="size-4" aria-hidden="true" /></span>
        <span className="min-w-0 flex-1"><span className="flex items-center gap-1 text-sm font-medium">{title}<ArrowRight className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" /></span><span className="mt-0.5 block text-xs leading-5 text-muted-foreground">{text}</span></span>
      </Link>)}</div>,
    },
    {
      title: "Comece por aqui",
      description: "O primeiro passo é buscar seus primeiros leads. Leva menos de um minuto.",
      body: <div className="rounded-2xl border bg-muted/30 p-4 text-sm">
        <p className="font-medium">Dica para uma boa busca</p>
        <p className="mt-1 text-muted-foreground">Diga o tipo de negócio e a cidade. Se quiser, diga também o que importa para você: “sem site”, “com WhatsApp”, “bem avaliados”.</p>
      </div>,
    },
  ]
  const current = steps[step]
  const last = step === steps.length - 1

  return <Dialog open={open} onOpenChange={(next) => { if (!next) close() }}>
    <DialogContent className="sm:max-w-lg">
      <DialogHeader>
        <p className="text-[11px] font-semibold uppercase tracking-[.18em] text-primary">Passo {step + 1} de {steps.length}</p>
        <DialogTitle className="text-xl">{current.title}</DialogTitle>
        <DialogDescription>{current.description}</DialogDescription>
      </DialogHeader>
      <div key={step} className="fx-rise">{current.body}</div>
      <div className="mt-2 flex items-center gap-2">
        <div className="flex gap-1.5" aria-hidden="true">{steps.map((_, index) => <span key={index} className={cn("h-1.5 rounded-full transition-all", index === step ? "w-6 bg-primary" : "w-1.5 bg-muted-foreground/30")} />)}</div>
        <div className="ml-auto flex gap-2">
          {step ? <Button type="button" variant="ghost" onClick={() => setStep(step - 1)}><ArrowLeft />Voltar</Button> : <Button type="button" variant="ghost" onClick={close}>Pular</Button>}
          {last ? <Button asChild onClick={close}><Link href={hunterExample(EXAMPLE.q, EXAMPLE.local)}><Search />Buscar meus primeiros leads</Link></Button>
            : <Button type="button" onClick={() => setStep(step + 1)}>Próximo<ArrowRight /></Button>}
        </div>
      </div>
    </DialogContent>
  </Dialog>
}

/** Small link to see the tour again. */
export function WelcomeTourLink({ className }: { className?: string }) {
  return <button type="button" onClick={() => window.dispatchEvent(new Event("kiara:welcome"))} className={className}>Ver as boas-vindas</button>
}
