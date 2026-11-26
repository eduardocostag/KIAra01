import { PresencialCapture } from "@/components/app-shell/presencial-capture"

export default function PresencialPage() {
  return <div className="mx-auto w-full max-w-4xl space-y-6">
    <header className="mx-auto max-w-xl">
      <h1 className="text-3xl font-medium tracking-tight">Contato presencial</h1>
      <p className="mt-1 text-sm text-muted-foreground">Conheceu alguém numa feira, visita ou reunião? Fotografe o cartão: a Kiara salva o contato e prepara a mensagem no WhatsApp.</p>
    </header>
    <PresencialCapture />
  </div>
}
