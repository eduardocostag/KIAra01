"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { BookOpen, Check, FileText, Globe2, Loader2, Plus, Search, Sun, Trash2, Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { prepareAttachment, CHAT_ATTACHMENT_ACCEPT } from "@/lib/chat-client"
import { growth, type KnowledgeItem, type Preset } from "@/lib/api/growth"
import { salesRequest, type SalesProfile } from "@/lib/api/sales"
import { cn } from "@/lib/utils"
import { MemoryPanel } from "./memory-panel"

const field = "h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary/50"
const KIND_ICON = { text: FileText, file: Upload, site: Globe2 }

function Section({ title, description, children, id }: { title: string; description: string; children: React.ReactNode; id: string }) {
  return <section aria-labelledby={id} className="kiara-soft-panel space-y-4 rounded-2xl border p-5 sm:p-6">
    <div><h2 id={id} className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
    {children}
  </section>
}

export function CompanyWorkspace() {
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [presets, setPresets] = useState<Preset[]>([])
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [usage, setUsage] = useState({ total: 0, limit: 400_000 })
  const [notice, setNotice] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState("")
  const [mode, setMode] = useState<"text" | "file" | "site">("text")
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [url, setUrl] = useState("")
  const [searches, setSearches] = useState<string[]>([])
  const [viewing, setViewing] = useState<{ title: string; content: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    try {
      const [nextProfile, nextPresets, knowledge] = await Promise.all([
        salesRequest<SalesProfile>("/api/sales/profile"), growth<{ items: Preset[] }>("sales/presets"),
        growth<{ items: KnowledgeItem[]; total_characters: number; limit_characters: number }>("knowledge")])
      setProfile(nextProfile); setPresets(nextPresets.items); setItems(knowledge.items); setUsage({ total: knowledge.total_characters, limit: knowledge.limit_characters })
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível carregar.") }
  }, [])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [load])

  async function act(key: string, work: () => Promise<unknown>, done: string) {
    setBusy(key); setError(""); setNotice("")
    try { await work(); setNotice(done); await load() }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível concluir.") }
    finally { setBusy("") }
  }

  async function saveProfile(patch: Partial<SalesProfile>, done = "Salvo.") {
    if (!profile) return
    const body: Partial<SalesProfile> = { ...profile, ...patch }
    delete body.updated_at
    await act("profile", () => salesRequest("/api/sales/profile", { method: "PUT", body: JSON.stringify(body) }), done)
  }

  async function addKnowledge(file?: File) {
    if (mode === "file" && file) {
      await act("add", async () => {
        const prepared = await prepareAttachment(file)
        if (prepared.kind === "image") throw new Error("Fotos não entram no conhecimento. Envie PDF, Word, planilha ou texto.")
        await growth("knowledge", { method: "POST", body: JSON.stringify({ kind: "file", title, file: { name: prepared.name, mime: prepared.mime, data_base64: prepared.data_base64 } }) })
      }, "Arquivo lido e guardado.")
    } else if (mode === "site") {
      await act("add", () => growth("knowledge", { method: "POST", body: JSON.stringify({ kind: "site", title, url }) }), "Página lida e guardada.")
    } else {
      await act("add", () => growth("knowledge", { method: "POST", body: JSON.stringify({ kind: "text", title, content }) }), "Guardado.")
    }
    setTitle(""); setContent(""); setUrl("")
  }

  const percent = Math.min(100, Math.round((usage.total / usage.limit) * 100))
  return <div className="space-y-6">
    {error ? <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}
    {notice ? <p role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 p-3 text-sm text-emerald-300">{notice}</p> : null}

    <Section id="segment" title="Seu segmento" description="A Kiara já começa com oferta, mensagens e perguntas frequentes do seu ramo. Você ajusta depois.">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{presets.map((preset) => <button key={preset.id} type="button" disabled={busy === "preset"}
        onClick={() => void act("preset", async () => { const result = await growth<{ searches: string[] }>(`sales/presets/${preset.id}`, { method: "POST" }); setSearches(Array.isArray(result?.searches) ? result.searches : []) }, `Segmento “${preset.label}” aplicado. Revise as perguntas frequentes abaixo.`)}
        className={cn("rounded-xl border p-3 text-left transition-colors hover:border-primary/50", profile?.segment === preset.id && "border-primary/60 bg-primary/10")}>
        <span className="flex items-center gap-1.5 text-sm font-medium">{profile?.segment === preset.id ? <Check className="size-4 text-primary" aria-hidden="true" /> : null}{preset.label}</span>
        <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{preset.offer}</span>
      </button>)}</div>
      {searches.length ? <div className="flex flex-wrap items-center gap-2 text-sm"><span className="text-muted-foreground">Buscas sugeridas:</span>{searches.map((query) => <Link key={query} href={`/app/hunter?${new URLSearchParams({ q: query })}`} className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs hover:border-primary/50"><Search className="size-3" aria-hidden="true" />{query}</Link>)}</div> : null}
      <p className="text-xs text-muted-foreground">Oferta, tom de voz e modelos de mensagem ficam em <Link href="/app/settings" className="-my-1.5 inline-block py-1.5 text-primary hover:underline">Configurações</Link>.</p>
    </Section>

    <Section id="knowledge" title="O que a Kiara sabe sobre o seu negócio" description="Catálogo, preços, prazos, perguntas frequentes, políticas e o seu site. A Kiara usa isso no chat, nas respostas do WhatsApp e nas mensagens de abordagem.">
      <div className="flex items-center gap-3 text-xs text-muted-foreground"><span className="h-1.5 w-40 overflow-hidden rounded-full bg-muted"><span className="block h-full bg-primary" style={{ width: `${percent}%` }} /></span>{percent}% do espaço usado</div>
      <div className="rounded-xl border p-3">
        <div role="tablist" aria-label="Como adicionar" className="mb-3 inline-flex rounded-full border p-0.5">{(["text", "file", "site"] as const).map((kind) => <button key={kind} type="button" role="tab" aria-selected={mode === kind} onClick={() => setMode(kind)} className={cn("rounded-full px-3 py-1 text-xs", mode === kind ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>{kind === "text" ? "Escrever" : kind === "file" ? "Arquivo" : "Site"}</button>)}</div>
        <div className="grid gap-2">
          <input className={field} value={title} onChange={(event) => setTitle(event.target.value)} placeholder={mode === "site" ? "Nome (opcional)" : "Título, por exemplo: Tabela de preços"} aria-label="Título" maxLength={200} />
          {mode === "text" ? <textarea className="min-h-28 w-full rounded-md border bg-background p-3 text-sm outline-none focus:border-primary/50" value={content} onChange={(event) => setContent(event.target.value)} placeholder="Ex.: Atendemos de segunda a sexta, das 9h às 18h. O site completo custa R$ 1.900 em até 6x." aria-label="Conteúdo" maxLength={60000} /> : null}
          {mode === "site" ? <input className={field} value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://seusite.com.br/servicos" aria-label="Endereço da página" inputMode="url" /> : null}
          {mode === "file" ? <input ref={fileRef} type="file" accept={CHAT_ATTACHMENT_ACCEPT} className="text-sm" aria-label="Arquivo" onChange={(event) => { const file = event.target.files?.[0]; if (file) void addKnowledge(file); event.target.value = "" }} /> : null}
          {mode !== "file" ? <Button type="button" className="w-fit" disabled={busy === "add" || (mode === "text" ? !content.trim() : !url.trim())} onClick={() => void addKnowledge()}>{busy === "add" ? <Loader2 className="animate-spin" /> : <Plus />}{mode === "site" ? "Ler a página" : "Guardar"}</Button>
            : busy === "add" ? <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Lendo o arquivo…</p> : null}
        </div>
      </div>
      {items.length ? <ul className="divide-y rounded-xl border">{items.map((item) => { const Icon = KIND_ICON[item.kind]; return <li key={item.id} className={cn("flex items-start gap-3 p-3", !item.enabled && "opacity-55")}>
        <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
        <button type="button" className="min-w-0 flex-1 text-left" onClick={() => void growth<{ title: string; content: string }>(`knowledge/${item.id}`).then(setViewing).catch(() => undefined)}>
          <span className="block truncate text-sm font-medium">{item.title}</span>
          <span className="line-clamp-1 text-xs text-muted-foreground">{item.preview}</span>
        </button>
        <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground"><input type="checkbox" checked={item.enabled} onChange={(event) => void act(item.id, () => growth(`knowledge/${item.id}`, { method: "PATCH", body: JSON.stringify({ enabled: event.target.checked }) }), event.target.checked ? "Ativado." : "Desativado: a Kiara não usa mais este item.")} />Usar</label>
        <button type="button" aria-label={`Excluir ${item.title}`} className="-m-1.5 shrink-0 p-1.5 text-muted-foreground hover:text-destructive" onClick={() => void act(item.id, () => growth(`knowledge/${item.id}`, { method: "DELETE" }), "Excluído.")}><Trash2 className="size-4" /></button>
      </li> })}</ul> : <p className="flex items-center gap-2 text-sm text-muted-foreground"><BookOpen className="size-4" aria-hidden="true" />Ainda vazio. Comece pelas perguntas que seus clientes mais fazem.</p>}
      {viewing ? <div className="rounded-xl border bg-muted/30 p-3"><div className="mb-2 flex items-center"><p className="flex-1 text-sm font-medium">{viewing.title}</p><button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setViewing(null)}>Fechar</button></div><pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5">{viewing.content}</pre></div> : null}
    </Section>

    <MemoryPanel />

    {profile ? <Section id="routine" title="Rotina automática" description="O que a Kiara faz sozinha por você todos os dias.">
      <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget)
        void saveProfile({ daily_summary: data.get("daily_summary") === "on", owner_whatsapp: String(data.get("owner_whatsapp") || "").replace(/\D/g, ""), daily_summary_hour: Number(data.get("hour") || 8),
          answer_anytime: data.get("answer_anytime") === "on", average_deal_cents: profile.average_deal_cents ?? 0 }, "Rotina salva.") }}>
        <label className="flex items-start gap-3"><input type="checkbox" name="daily_summary" defaultChecked={profile.daily_summary} className="mt-1" /><span><span className="flex items-center gap-1.5 text-sm font-medium"><Sun className="size-4 text-amber-400" aria-hidden="true" />Resumo diário no meu WhatsApp</span><span className="text-xs text-muted-foreground">Leads quentes para ligar, acompanhamentos do dia e negociações paradas, toda manhã.</span></span></label>
        <div className="grid gap-3 pl-7 sm:grid-cols-2"><label className="grid gap-1 text-sm">Meu WhatsApp (com DDD)<input name="owner_whatsapp" className={field} defaultValue={profile.owner_whatsapp} placeholder="51999990000" inputMode="tel" /></label>
          <label className="grid gap-1 text-sm">Horário<select name="hour" defaultValue={profile.daily_summary_hour ?? 8} className={field}>{[6, 7, 8, 9, 10, 11, 12].map((hour) => <option key={hour} value={hour}>{hour}h</option>)}</select></label></div>
        <label className="flex items-start gap-3"><input type="checkbox" name="answer_anytime" defaultChecked={profile.answer_anytime} className="mt-1" /><span><span className="text-sm font-medium">Atender 24 horas no WhatsApp</span><span className="block text-xs text-muted-foreground">Quem escrever fora do horário recebe resposta na hora. Acompanhamentos continuam só no horário comercial. Vale quando o atendimento automático do WhatsApp está ligado.</span></span></label>
        <Button type="submit" disabled={busy === "profile"}>{busy === "profile" ? <Loader2 className="animate-spin" /> : <Check />}Salvar rotina</Button>
      </form>
    </Section> : null}
  </div>
}
