import { ExternalLink, MessageCircle, Phone } from "lucide-react"
import { Button } from "@/components/ui/button"
import { phoneHref, safePublicUrl, safeWhatsAppUrl, type PipelineEntry } from "@/lib/api/pipeline"

export function LeadContactActions({ consumer }: { consumer: PipelineEntry["consumer"] }) {
  const whatsapp = safeWhatsAppUrl(consumer.whatsapp_url)
  const phone = phoneHref(consumer.phone)
  const source = safePublicUrl(consumer.source_url)
  return <div className="flex flex-wrap items-center gap-2">
    {whatsapp ? <Button asChild size="sm"><a href={whatsapp} target="_blank" rel="noreferrer" aria-label={`Abrir WhatsApp de ${consumer.display_name}`}><MessageCircle />WhatsApp <ExternalLink className="size-3" /></a></Button> :
      phone ? <Button asChild variant="outline" size="sm"><a href={phone} aria-label={`Ligar para ${consumer.display_name}`}><Phone />{consumer.phone}</a></Button> : <span className="text-xs text-muted-foreground">Contato não publicado</span>}
    {source && <Button asChild variant="ghost" size="sm"><a href={source} target="_blank" rel="noreferrer" aria-label={`Ver fonte de ${consumer.display_name}`}>Fonte <ExternalLink className="size-3" /></a></Button>}
  </div>
}
