"use client"

import { useMemo, useState } from "react"
import { AtSign, Check, Copy, ExternalLink, MessageCircle, Phone, Send, ShieldCheck, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { instagramProfileUrl, phoneHref, safePublicUrl, type PipelineEntry, whatsappComposerUrl } from "@/lib/api/pipeline"

const DEFAULT_TEMPLATE = "Olá! Tudo bem? Meu nome é {remetente} e encontrei {nome} durante uma pesquisa sobre {nicho} em {cidade}. Notei uma oportunidade para fortalecer sua presença digital e preparei uma sugestão breve. Posso compartilhar por aqui?"

function personalize(template: string, sender: string, consumer: PipelineEntry["consumer"]): string {
  const values: Record<string, string> = {
    remetente: sender.trim() || "[seu nome ou empresa]",
    nome: consumer.display_name,
    nicho: consumer.research_query?.trim() || "seu segmento",
    cidade: consumer.address?.trim() || "sua região",
  }
  return template.replace(/\{(remetente|nome|nicho|cidade)\}/g, (_, key: string) => values[key])
}

export function LeadContactActions({ consumer }: { consumer: PipelineEntry["consumer"] }) {
  const [sender, setSender] = useState("")
  const [template, setTemplate] = useState(DEFAULT_TEMPLATE)
  const [copied, setCopied] = useState(false)
  const message = personalize(template, sender, consumer)
  const whatsapp = useMemo(() => whatsappComposerUrl(consumer.phone, consumer.whatsapp_url, message), [consumer.phone, consumer.whatsapp_url, message])
  const instagram = instagramProfileUrl(consumer.instagram_username)
  const phone = phoneHref(consumer.phone)
  const source = safePublicUrl(consumer.source_url)
  const ready = Boolean(sender.trim() && message.trim())

  async function copyMessage() {
    await navigator.clipboard.writeText(message)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Dialog>
        <DialogTrigger asChild><Button size="sm" className="shadow-sm"><Sparkles /> Preparar abordagem</Button></DialogTrigger>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <div className="mb-1 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Send className="size-5" /></div>
            <DialogTitle className="text-xl">Abordagem para {consumer.display_name}</DialogTitle>
            <DialogDescription>Personalize a mensagem, revise e abra o canal. A Kiara não envia nada sem sua confirmação.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-5 py-2">
            <div className="grid gap-2">
              <Label htmlFor={`sender-${consumer.id}`}>Seu nome ou empresa</Label>
              <Input id={`sender-${consumer.id}`} value={sender} onChange={(event) => setSender(event.target.value)} placeholder="Ex.: Eduardo, da Agência Kiara" autoComplete="organization" />
            </div>
            <div className="grid gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Label htmlFor={`message-${consumer.id}`}>Modelo de mensagem</Label>
                <span className="text-xs text-muted-foreground">Use: {'{remetente}'} {'{nome}'} {'{nicho}'} {'{cidade}'}</span>
              </div>
              <Textarea id={`message-${consumer.id}`} value={template} onChange={(event) => setTemplate(event.target.value)} className="min-h-32 resize-y leading-relaxed" />
              <div className="rounded-xl border bg-muted/35 p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Prévia personalizada</p>
                <p className="whitespace-pre-wrap leading-relaxed">{message}</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border p-3">
                <div className="flex items-center gap-2 font-medium"><MessageCircle className="size-4 text-emerald-600" /> WhatsApp</div>
                <p className="mt-1 text-xs text-muted-foreground">{whatsapp?.confirmed ? "Canal confirmado na fonte." : whatsapp ? "Número encontrado; confirme se pertence ao WhatsApp." : "Nenhum número compatível disponível."}</p>
              </div>
              <div className="rounded-xl border p-3">
                <div className="flex items-center gap-2 font-medium"><AtSign className="size-4 text-fuchsia-600" /> Instagram</div>
                <p className="mt-1 text-xs text-muted-foreground">{instagram ? `Perfil @${consumer.instagram_username?.replace(/^@/, "")} disponível.` : "Nenhum perfil público disponível."}</p>
              </div>
            </div>
            <div className="flex items-start gap-2 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-amber-600" />
              <p>Contate apenas pessoas com contexto legítimo, respeite recusas e evite disparos em massa. WhatsApp e Instagram serão abertos para você revisar e confirmar o envio manualmente.</p>
            </div>
          </div>
          <DialogFooter className="flex-wrap">
            <Button variant="outline" onClick={copyMessage} disabled={!message.trim()}>{copied ? <Check /> : <Copy />} {copied ? "Copiada" : "Copiar mensagem"}</Button>
            {instagram ? <Button variant="outline" asChild disabled={!ready}><a href={ready ? instagram : undefined} target="_blank" rel="noreferrer" aria-disabled={!ready} onClick={(event) => { if (!ready) event.preventDefault(); else void copyMessage() }}><AtSign /> Copiar e abrir Instagram</a></Button> : null}
            {whatsapp ? <Button asChild disabled={!ready}><a href={ready ? whatsapp.url : undefined} target="_blank" rel="noreferrer" aria-disabled={!ready} onClick={(event) => { if (!ready) event.preventDefault() }}><MessageCircle /> {whatsapp.confirmed ? "Abrir WhatsApp" : "Tentar no WhatsApp"}</a></Button> : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {phone ? <Button asChild variant="outline" size="sm"><a href={phone} aria-label={`Ligar para ${consumer.display_name}`}><Phone /> Ligar</a></Button> : null}
      {source ? <Button asChild variant="ghost" size="sm"><a href={source} target="_blank" rel="noreferrer" aria-label={`Ver fonte de ${consumer.display_name}`}>Fonte <ExternalLink className="size-3" /></a></Button> : null}
      {!whatsapp && !instagram && !phone ? <span className="text-xs text-muted-foreground">Contato não publicado</span> : null}
    </div>
  )
}
