"use client"

import { useMemo, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { AtSign, Check, Copy, ExternalLink, LoaderCircle, MessageCircle, Send, ShieldCheck, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { instagramProfileUrl, safePublicUrl, type PipelineEntry, whatsappComposerUrl } from "@/lib/api/pipeline"
import { salesRequest, type SalesProfile, templateLabels } from "@/lib/api/sales"

const FALLBACK = "Olá! Tudo bem? Meu nome é {remetente} e encontrei {nome} durante uma pesquisa sobre {nicho} em {cidade}. Posso compartilhar uma sugestão breve?"

function personalize(template: string, sender: string, profile: SalesProfile | null, consumer: PipelineEntry["consumer"]): string {
  const values: Record<string, string> = { remetente: sender.trim() || "[seu nome ou empresa]", nome: consumer.display_name, nicho: consumer.research_query?.trim() || "seu segmento", cidade: consumer.address?.trim() || "sua região", oferta: profile?.offer.trim() || "uma solução para sua presença digital" }
  return template.replace(/\{(remetente|nome|nicho|cidade|oferta)\}/g, (_, key: string) => values[key])
}

export function LeadContactActions({ entry, onRecorded }: { entry: PipelineEntry; onRecorded?: () => void | Promise<void> }) {
  const router = useRouter()
  const { consumer } = entry
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [sender, setSender] = useState("")
  const [templateKey, setTemplateKey] = useState("first_contact")
  const [template, setTemplate] = useState(FALLBACK)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [openedChannel, setOpenedChannel] = useState<"whatsapp" | "instagram" | null>(null)
  const [notice, setNotice] = useState("")
  const message = personalize(template, sender, profile, consumer)
  const whatsapp = useMemo(() => whatsappComposerUrl(consumer.phone, consumer.whatsapp_url, message), [consumer.phone, consumer.whatsapp_url, message])
  const instagram = instagramProfileUrl(consumer.instagram_username)
  const source = safePublicUrl(consumer.source_url)
  const ready = Boolean(sender.trim() && message.trim())

  async function loadProfile(open: boolean) {
    if (!open || profile || loading) return
    setLoading(true); setNotice("")
    try { const value = await salesRequest<SalesProfile>("/api/sales/profile"); setProfile(value); setSender(value.sender_name); setTemplate(value.templates.first_contact || FALLBACK) }
    catch (error) { setNotice(error instanceof Error ? error.message : "Não foi possível carregar as configurações.") }
    finally { setLoading(false) }
  }
  function chooseTemplate(key: string) { setTemplateKey(key); setTemplate(profile?.templates[key] || FALLBACK) }
  async function copyMessage() { await navigator.clipboard.writeText(message); setCopied(true); window.setTimeout(() => setCopied(false), 1800) }
  async function record(status: "opened" | "sent", channel: "whatsapp" | "instagram") {
    await salesRequest("/api/sales/activities", { method: "POST", body: JSON.stringify({ pipeline_entry_id: entry.id, channel, status, body: message, follow_up_hours: status === "sent" ? profile?.follow_up_hours : null }) })
  }
  function openChannel(channel: "whatsapp" | "instagram", url: string) { window.open(url, "_blank", "noopener,noreferrer"); setOpenedChannel(channel); setNotice("Canal aberto. Depois do envio, volte aqui e confirme para registrar no CRM."); void record("opened", channel).catch(() => undefined); if (channel === "instagram") void copyMessage() }
  async function confirmSent() {
    if (!openedChannel) return
    setSaving(true); setNotice("")
    try { await record("sent", openedChannel); setNotice(`Envio confirmado. Lead movido para Em contato e follow-up agendado para ${profile?.follow_up_hours ?? 48} horas.`); setOpenedChannel(null); if (onRecorded) await onRecorded(); else router.refresh() }
    catch (error) { setNotice(error instanceof Error ? error.message : "Não foi possível registrar o envio.") }
    finally { setSaving(false) }
  }

  return <div className="flex flex-wrap items-center gap-2">
    <Dialog onOpenChange={(open) => void loadProfile(open)}>
      <DialogTrigger asChild><Button size="sm" className="shadow-sm"><Sparkles />Preparar abordagem</Button></DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader><div className="mb-1 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Send className="size-5" /></div><DialogTitle className="text-xl">Abordagem para {consumer.display_name}</DialogTitle><DialogDescription>Escolha um modelo, revise e abra o canal. O envio só é registrado após sua confirmação.</DialogDescription></DialogHeader>
        {loading ? <div className="flex min-h-52 items-center justify-center"><LoaderCircle className="animate-spin" /><span className="ml-2">Carregando seus modelos…</span></div> : <div className="grid gap-5 py-2">
          <div className="grid gap-2"><Label htmlFor={`sender-${consumer.id}`}>Quem está entrando em contato?</Label><Input id={`sender-${consumer.id}`} value={sender} onChange={(event) => setSender(event.target.value)} placeholder="Seu nome ou empresa" autoComplete="organization" /><p className="text-xs text-muted-foreground">Você pode preencher aqui mesmo; para reutilizar automaticamente, salve em Configurações.</p></div>
          <div className="grid gap-2"><Label>Tipo de abordagem</Label><Select value={templateKey} onValueChange={chooseTemplate}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent>{Object.keys(profile?.templates || { first_contact: FALLBACK }).map((key) => <SelectItem key={key} value={key}>{templateLabels[key] || key}</SelectItem>)}</SelectContent></Select></div>
          <div className="grid gap-2"><Label htmlFor={`message-${consumer.id}`}>Mensagem</Label><Textarea id={`message-${consumer.id}`} value={template} onChange={(event) => setTemplate(event.target.value)} className="min-h-32 resize-y leading-relaxed" /><div className="rounded-xl border bg-muted/35 p-4"><p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Prévia personalizada</p><p className="whitespace-pre-wrap leading-relaxed">{message}</p></div></div>
          <div className="grid gap-3 sm:grid-cols-2"><Channel icon={<MessageCircle className="size-4 text-emerald-600" />} title="WhatsApp" text={whatsapp?.confirmed ? "Canal confirmado na fonte." : whatsapp ? "Número encontrado; confirme se pertence ao WhatsApp." : "Nenhum número compatível disponível."} /><Channel icon={<AtSign className="size-4 text-fuchsia-600" />} title="Instagram" text={instagram ? `Perfil @${consumer.instagram_username?.replace(/^@/, "")} disponível.` : "Nenhum perfil público disponível."} /></div>
          <div className="flex items-start gap-2 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3 text-xs text-muted-foreground"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-amber-600" /><p>Respeite recusas e evite disparos em massa. A Kiara abre o canal e aguarda sua confirmação; ela não pressiona o botão de envio.</p></div>
          {notice ? <p role="status" className="rounded-lg border bg-muted/40 p-3 text-sm">{notice}</p> : null}
        </div>}
        <DialogFooter className="flex-wrap"><Button variant="outline" onClick={() => void copyMessage()} disabled={!message.trim()}>{copied ? <Check /> : <Copy />}{copied ? "Copiada" : "Copiar"}</Button>{instagram ? <Button variant="outline" disabled={!ready} onClick={() => openChannel("instagram", instagram)}><AtSign />Copiar e abrir Instagram</Button> : null}{whatsapp ? <Button disabled={!ready} onClick={() => openChannel("whatsapp", whatsapp.url)}><MessageCircle />{whatsapp.confirmed ? "Abrir WhatsApp" : "Tentar no WhatsApp"}</Button> : null}{openedChannel ? <Button onClick={() => void confirmSent()} disabled={saving}>{saving ? <LoaderCircle className="animate-spin" /> : <Check />}Confirmar que enviei</Button> : null}</DialogFooter>
      </DialogContent>
    </Dialog>
    {source ? <Button asChild variant="ghost" size="sm"><a href={source} target="_blank" rel="noreferrer" aria-label={`Ver fonte de ${consumer.display_name}`}>Fonte<ExternalLink className="size-3" /></a></Button> : null}
    {!whatsapp && !instagram ? <span className="text-xs text-muted-foreground">WhatsApp ou Instagram não encontrados</span> : null}
  </div>
}

function Channel({ icon, title, text }: { icon: ReactNode; title: string; text: string }) { return <div className="rounded-xl border p-3"><div className="flex items-center gap-2 font-medium">{icon}{title}</div><p className="mt-1 text-xs text-muted-foreground">{text}</p></div> }
