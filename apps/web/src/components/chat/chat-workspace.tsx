"use client"

import { useEffect, useRef, useState, useSyncExternalStore } from "react"
import { ArrowUp, AudioLines, Bot, ChartNoAxesCombined, Check, ChevronsRight, Copy, Download, FileDown, FileSpreadsheet, ExternalLink, FileText, Globe2, ImagePlus, LoaderCircle, MessageCircle, Mic, Paperclip, Pencil, Pin, PinOff, Plus, RefreshCw, RotateCcw, Search, Settings2, Share2, Sparkles, Square, Trash2, Upload, Video, Volume2, Workflow, X } from "lucide-react"
import { ImmersiveShell } from "@/components/app-shell/immersive-shell"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { blobBase64, CHAT_ATTACHMENT_ACCEPT, chatRequest, fetchVideo, imageThumbnail, isolatedHtml, parseChatReply, parseChatStatus, parseVideoJob, prepareAttachment, streamChat, StreamUnavailableError, validateChatAudio, type ChatAction, type ChatArtifact, type ChatAttachment, type ChatImage, type ChatSource, type ChatVideoJob, type ChatMessage, type ChatMode, type ChatPlan, type ChatStatus, type ChatTransport } from "@/lib/chat-client"
import { downloadWord, looksUnfinished, printAnswer, whatsappText } from "@/lib/chat-export"
import { parseBlocks, plainText, type Inline } from "@/lib/chat-markdown"
import { cn } from "@/lib/utils"
import { pollVideoJob } from "@/lib/video-polling"
import { femininePortugueseVoice, VoiceConversation, type VoiceBackends } from "./voice-conversation"

function InlineText({ parts }: { parts: Inline[] }) {
  return <>{parts.map((part, index) => part.href
    ? <a key={index} href={part.href} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2">{part.text}</a>
    : part.code
    ? <code key={index} className="rounded bg-muted px-1 py-0.5 text-[0.9em]">{part.text}</code>
    : part.bold || part.italic ? <span key={index} className={cn(part.bold && "font-semibold", part.italic && "italic")}>{part.text}</span>
      : <span key={index}>{part.text}</span>)}</>
}

/** Kiara's reply as clean, formatted text: no raw "##", "**" or table pipes. */
function KiaraText({ text }: { text: string }) {
  return <div className="space-y-3 break-words text-[15px] leading-7">{parseBlocks(text).map((block, index) => {
    if (block.kind === "heading") return <p key={index} className="pt-1 font-semibold"><InlineText parts={block.inlines} /></p>
    if (block.kind === "paragraph") return <p key={index} className="whitespace-pre-wrap"><InlineText parts={block.inlines} /></p>
    if (block.kind === "quote") return <p key={index} className="border-l-2 pl-3 text-muted-foreground"><InlineText parts={block.inlines} /></p>
    if (block.kind === "code") return <pre key={index} className="overflow-x-auto rounded-xl bg-muted p-3 text-sm leading-6"><code>{block.text}</code></pre>
    if (block.kind === "table") return <div key={index} className="overflow-x-auto rounded-xl border"><table className="w-full text-sm">
      {block.header.length ? <thead className="bg-muted/50"><tr>{block.header.map((cell, column) => <th key={column} className="px-3 py-2 text-left font-medium"><InlineText parts={cell} /></th>)}</tr></thead> : null}
      <tbody>{block.rows.map((row, line) => <tr key={line} className="border-t">{row.map((cell, column) => <td key={column} className="px-3 py-2 align-top"><InlineText parts={cell} /></td>)}</tr>)}</tbody>
    </table></div>
    if (block.kind !== "bullets" && block.kind !== "numbers") return null
    const List = block.kind === "numbers" ? "ol" : "ul"
    return <List key={index} className={cn("space-y-1.5 pl-5", block.kind === "numbers" ? "list-decimal" : "list-disc")}>{block.items.map((item, line) => <li key={line}><InlineText parts={item} /></li>)}</List>
  })}</div>
}

type SentFile = { name: string; kind: ChatAttachment["kind"]; preview?: string }
type Message = ChatMessage & { id: string; artifact?: ChatArtifact; plan?: ChatPlan; video?: ChatVideoJob; image?: ChatImage
  sources?: ChatSource[]; actions?: ChatAction[]; files?: SentFile[]; streaming?: boolean; status?: string; interrupted?: boolean }
type SentPhoto = NonNullable<ChatMessage["attachments"]>[number]

/** A file chosen for the next message (with remove) or already sent (in the bubble); click to see it. */
function AttachmentChip({ file, onRemove, onOpen }: { file: SentFile; onRemove?: () => void; onOpen?: () => void }) {
  const body = <>
    {/* eslint-disable-next-line @next/next/no-img-element -- local preview made in this browser */}
    {file.preview ? <img src={file.preview} alt="" className="size-8 rounded-lg object-cover" /> : file.kind === "sheet" ? <FileSpreadsheet className="ml-1 size-4 text-primary" aria-hidden="true" /> : <FileText className="ml-1 size-4 text-primary" aria-hidden="true" />}
    <span className="max-w-40 truncate">{file.name}</span>
  </>
  return <span className="flex items-center gap-2 rounded-xl border bg-card py-1 pl-1 pr-2 text-xs transition-colors hover:border-primary/40">
    {onOpen ? <button type="button" onClick={onOpen} className="flex items-center gap-2 text-left" aria-label={`Ver ${file.name}`}>{body}</button> : body}
    {onRemove ? <button type="button" onClick={onRemove} aria-label={`Remover ${file.name}`} className="text-muted-foreground hover:text-foreground"><X className="size-3.5" /></button> : null}
  </span>
}
type Conversation = { id: string; title: string; updatedAt: number; messages: Message[]; pinned?: boolean }
type FilePreview = { name: string; kind: SentFile["kind"]; image?: string; text?: string; sheets?: string[]; pending?: boolean }

/** The part of a message's kept text that belongs to one file (sections start with "[name, ...]"). */
function fileSection(context: string | undefined, name: string): string {
  if (!context) return ""
  const start = context.indexOf(`[${name},`)
  if (start < 0) return ""
  const rest = context.slice(start)
  const body = rest.slice(rest.indexOf("]\n") + 2)
  const next = body.search(/\n\n\[[^\]\n]+, (PDF|documento Word|planilha|planilha CSV|arquivo de texto)\]\n/)
  return (next >= 0 ? body.slice(0, next) : body).trim()
}

/** The continuation is glued to what was already written (the model usually resumes mid-sentence). */
function joinContinuation(previous: string, next: string): string {
  if (!next) return previous
  return previous + (/[.!?:;,]$/.test(previous) && /^[\p{L}\d]/u.test(next) ? " " : "") + next
}

const fold = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()

const modes = [
  { id: "chat", label: "Conversar", icon: MessageCircle, placeholder: "Pergunte qualquer coisa à Kiara" },
  { id: "image", label: "Imagem", icon: ImagePlus, placeholder: "Descreva a imagem que você quer criar" },
  { id: "video", label: "Vídeo", icon: Video, placeholder: "Descreva o vídeo: para quem é, o que mostrar e o tom" },
  { id: "website", label: "Site", icon: Globe2, placeholder: "Descreva o site: público, páginas e identidade" },
  { id: "dashboard", label: "Dashboard", icon: ChartNoAxesCombined, placeholder: "Descreva os indicadores e filtros do dashboard" },
  { id: "automation", label: "Tarefa", icon: Workflow, placeholder: "Descreva o objetivo e a Kiara prepara um plano" },
] satisfies { id: ChatMode; label: string; icon: typeof MessageCircle; placeholder: string }[]
const capabilityLabels: Record<string, string> = { chat: "Conversa e análise", speech: "Voz da Kiara", transcribe: "Receber áudio", image: "Imagens", video: "Vídeos", website: "Sites", dashboard: "Dashboards", automation: "Automação" }
const suggestions = [
  { mode: "chat" as const, title: "Organizar prioridades", text: "Ajude a organizar as prioridades da minha operação e sugira próximos passos." },
  { mode: "website" as const, title: "Criar um site", text: "Crie um site institucional responsivo com apresentação, serviços, perguntas frequentes e contato." },
  { mode: "dashboard" as const, title: "Montar um dashboard", text: "Crie um dashboard comercial com indicadores e filtros. Identifique claramente os dados de demonstração." },
  { mode: "video" as const, title: "Criar um vídeo curto", text: "Crie um vídeo vertical de 6 segundos de ondas do mar ao pôr do sol, com luz dourada, para o Reels." },
  { mode: "automation" as const, title: "Planejar uma tarefa", text: "Prepare um plano revisável para organizar arquivos e automatizar tarefas recorrentes no computador." },
]
const HISTORY_LIMIT = 30

/** `photos`: the pictures sent earlier while this page is open (by message id); the two latest go again with their message. */
function boundedHistory(messages: Message[], photos?: Map<string, SentPhoto[]>, photoBudget = 0): ChatMessage[] {
  let remaining = 35_000
  let kept = 38_000
  let recentPhotos = 2
  return messages.filter((message) => message.content.trim()).slice(-24).reverse().flatMap((message) => {
    if (remaining <= 0) return []
    const extra: Partial<ChatMessage> = {}
    if (message.role === "user" && message.file_context && kept > 0) {
      extra.file_context = message.file_context.slice(0, Math.min(20_000, kept))
      kept -= extra.file_context.length
    }
    const sent = message.role === "user" ? photos?.get(message.id) : undefined
    if (sent?.length && recentPhotos > 0) {
      const size = sent.reduce((sum, photo) => sum + photo.data_base64.length, 0)
      if (size <= photoBudget) { extra.attachments = sent; photoBudget -= size; recentPhotos -= 1 }
    }
    // The picture's description goes with it, so "agora mais azul" can redraw the same scene.
    const files = message.files?.length ? `\n\n[anexos enviados nesta mensagem: ${message.files.map((file) => file.name).join(", ")}]` : ""
    const text = (message.image?.prompt ? `${message.content}\n\n(imagem enviada: ${message.image.prompt})` : message.content) + files
    const content = text.slice(0, Math.min(10_000, remaining))
    remaining -= content.length
    return [{ role: message.role, content, ...extra }]
  }).reverse()
}

function readHistory(key: string): Conversation[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "[]")
    return Array.isArray(value) ? value.filter((item): item is Conversation => typeof item?.id === "string" && Array.isArray(item?.messages)) : []
  } catch { return [] }
}

function writeHistory(key: string, conversations: Conversation[]) {
  // Generated HTML can be large; history keeps the text and plans only.
  // Pictures keep only their small copy: full images would fill the browser's storage.
  // The text of attached documents is kept only in the latest conversations, so storage does not fill up.
  const slim = conversations.slice(0, HISTORY_LIMIT).map((conversation, position) => ({ ...conversation, messages: conversation.messages.filter((message) => !message.streaming || message.content).map(({ artifact, image, ...rest }) => {
    const message = { ...rest, streaming: undefined, status: undefined, ...(position >= 5 ? { file_context: undefined } : {}) }  // live-typing state is never saved
    return {
    ...(artifact ? { ...message, content: `${message.content}\n\n[Arquivo gerado: ${artifact.name}]` } : message),
    ...(image?.thumb ? { image: { src: image.thumb, thumb: image.thumb, prompt: image.prompt } } : {}),
  } }) }))
  try { localStorage.setItem(key, JSON.stringify(slim)) } catch { /* Storage full or blocked: history stays in memory. */ }
}

function saveArtifact(artifact: ChatArtifact) {
  const url = URL.createObjectURL(new Blob([artifact.content], { type: artifact.mime }))
  const link = document.createElement("a")
  link.href = url
  link.download = artifact.name.endsWith(".html") ? artifact.name : `${artifact.name}.html`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function Artifact({ artifact }: { artifact: ChatArtifact }) {
  const [preview, setPreview] = useState(false)
  return <section className="mt-3 overflow-hidden rounded-2xl border" aria-label="Arquivo gerado">
    <div className="flex flex-wrap items-center gap-3 p-3">
      <Globe2 className="size-5 text-primary" aria-hidden="true" />
      <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{artifact.name}</p><p className="text-xs text-muted-foreground">HTML para revisar e baixar</p></div>
      <Button type="button" size="sm" variant="outline" onClick={() => setPreview(!preview)}>{preview ? "Fechar" : "Prévia"}</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => saveArtifact(artifact)} aria-label={`Baixar ${artifact.name}`}><Download aria-hidden="true" />Baixar</Button>
    </div>
    {preview && <iframe className="h-[480px] w-full border-t bg-white" title={`Prévia de ${artifact.name}`} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={isolatedHtml(artifact.content)} />}
  </section>
}

/** A picture Kiara drew; after a reload only the small copy remains, so download is offered while the full one is here. */
function Picture({ image }: { image: ChatImage }) {
  const full = image.src !== image.thumb
  return <figure className="mt-3 w-full max-w-md overflow-hidden rounded-2xl border bg-muted/30">
    {/* eslint-disable-next-line @next/next/no-img-element -- data URL generated in this conversation */}
    <img src={image.src} alt={image.prompt || "Imagem criada pela Kiara"} className="block h-auto max-h-[70vh] w-full object-contain" />
    <figcaption className="flex items-center gap-2 p-2 pl-3">
      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{full ? "Imagem criada pela Kiara" : "Prévia salva neste navegador"}</span>
      {full ? <Button type="button" size="sm" variant="outline" asChild><a href={image.src} download="kiara-imagem.jpg"><Download aria-hidden="true" />Baixar</a></Button> : null}
    </figcaption>
  </figure>
}

/** A presentation video being produced on this computer: progress while rendering, player when done. */
function VideoJob({ initial, transport }: { initial: ChatVideoJob; transport: ChatTransport }) {
  const [job, setJob] = useState(initial)
  const [url, setUrl] = useState("")
  const [error, setError] = useState("")
  const [pollPaused, setPollPaused] = useState(false)
  const [pollAttempt, setPollAttempt] = useState(0)
  useEffect(() => {
    if (initial.status !== "running") return
    return pollVideoJob({
      read: async (signal) => {
        const statusSignal = AbortSignal.any([signal, AbortSignal.timeout(30_000)])
        const payload = await chatRequest(transport, "video", { action: "status", job_id: initial.id }, statusSignal) as { video?: unknown }
        return parseVideoJob(payload.video)
      },
      onUpdate: (current) => { setJob(current); setError(""); setPollPaused(false) },
      onError: (reason) => setError(reason instanceof Error ? reason.message : "Não foi possível acompanhar o vídeo."),
      onPaused: () => setPollPaused(true),
    })
  }, [initial.id, initial.status, transport, pollAttempt])
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])
  async function load() {
    setError("")
    try { setUrl(URL.createObjectURL(await fetchVideo(job.id, transport))) } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível abrir o vídeo.") }
  }
  const name = `kiara-video-${job.id.slice(0, 8)}.mp4`
  return <section className="mt-3 overflow-hidden rounded-2xl border" aria-label="Vídeo da Kiara">
    <div className="flex flex-wrap items-center gap-3 p-3">
      <Video className="size-5 text-primary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{job.title || "Vídeo da Kiara"}</p>
        <p className="text-xs text-muted-foreground" role="status">{job.status === "failed" ? job.error : job.status === "done" ? `Pronto${job.duration ? ` · ${job.duration < 60 ? `${Math.round(job.duration)}s` : `${Math.floor(job.duration / 60)}min${String(Math.round(job.duration % 60)).padStart(2, "0")}`}` : ""}${transport === "local" ? " · gerado neste computador" : ""}` : job.message}</p>
      </div>
      {job.status === "done" && !url ? <Button type="button" size="sm" variant="outline" onClick={() => void load()}><Video aria-hidden="true" />Assistir</Button> : null}
      {pollPaused && job.status === "running" ? <Button type="button" size="sm" variant="outline" onClick={() => { setPollPaused(false); setError(""); setPollAttempt((attempt) => attempt + 1) }}><RefreshCw aria-hidden="true" />Retomar acompanhamento</Button> : null}
      {url ? <Button type="button" size="sm" variant="outline" asChild><a href={url} download={name}><Download aria-hidden="true" />Baixar</a></Button> : null}
    </div>
    {job.status === "running" ? <div className="h-1 bg-muted"><div className="h-full bg-primary transition-[width] duration-700" style={{ width: `${Math.max(3, job.progress * 100)}%` }} /></div> : null}
    {url ? <video className="max-h-[70vh] w-full border-t bg-black object-contain" src={url} controls autoPlay loop playsInline /> : null}
    {job.status === "done" && job.warnings.length ? <p className="border-t px-3 py-2 text-xs text-muted-foreground">{job.warnings[0]}</p> : null}
    {error ? <p className="border-t px-3 py-2 text-xs text-destructive">{error}</p> : null}
  </section>
}

const noop = () => () => {}

/** Opens the first site of a new answer by itself (like the old desktop Kiara). Browsers may block a tab opened
 *  after the answer arrives; the button under the message always works. App links (vscode:, obsidian:) wait for a tap. */
function openFirst(actions?: ChatAction[]) {
  const first = actions?.[0]
  if (!first || !first.url.startsWith("https://")) return
  try { window.open(first.url, "_blank", "noopener,noreferrer") } catch { /* Blocked: the button stays. */ }
}

/** `isAdmin` shows the technical layer (model, connection, resources); everyone else only sees Kiara. */
export function ChatWorkspace({ userId = "preview", isAdmin = false }: { userId?: string; isAdmin?: boolean }) {
  const storageKey = `kiara-chat-history:${userId}`
  const browserVoice = useSyncExternalStore(noop, () => "speechSynthesis" in window, () => false)
  const [transport, setTransport] = useState<ChatTransport>("cloud")
  const [status, setStatus] = useState<ChatStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [connectionError, setConnectionError] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [mode, setMode] = useState<ChatMode>("chat")
  const [draft, setDraft] = useState("")
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState("")
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [audioUrl, setAudioUrl] = useState("")
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [copied, setCopied] = useState("")
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [editingId, setEditingId] = useState("")
  const [preview, setPreview] = useState<FilePreview | null>(null)
  const [dragging, setDragging] = useState(false)
  const [query, setQuery] = useState("")
  const dragDepth = useRef(0)
  // Voice turns run outside React's render cycle; refs give them the latest conversation.
  const conversationsRef = useRef<Conversation[]>([])
  const activeIdRef = useRef("")
  const abortRef = useRef<AbortController | null>(null)
  const statusAbortRef = useRef<AbortController | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const audioRef = useRef<HTMLAudioElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const attachRef = useRef<HTMLInputElement>(null)
  const photosRef = useRef(new Map<string, SentPhoto[]>())  // photos sent while this page is open, never saved
  const [attachments, setAttachments] = useState<ChatAttachment[]>([])
  const draftRef = useRef<HTMLTextAreaElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const recordTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const activeMode = modes.find((item) => item.id === mode)!
  const active = conversations.find((item) => item.id === activeId)
  const messages = active?.messages ?? []
  const capability = (id: string) => status?.capabilities.find((item) => item.id === id)
  const available = Boolean(status?.connected && capability(mode === "automation" ? "chat" : mode)?.available)
  const canTranscribe = Boolean(status?.connected && capability("transcribe")?.available)

  // History lives in this browser only, separated per signed-in user.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { const history = readHistory(storageKey); conversationsRef.current = history; setConversations(history) }, [storageKey])
  useEffect(() => { activeIdRef.current = activeId }, [activeId])
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }) }, [messages.length, busy])

  useEffect(() => {
    mountedRef.current = true
    const controller = new AbortController()
    statusAbortRef.current = controller
    async function discover() {
      let cloudError = ""
      try {
        const cloud = parseChatStatus(await chatRequest("cloud", "status", {}, controller.signal))
        if (cloud.connected && cloud.capabilities.some((item) => item.id === "chat" && item.available)) {
          if (!controller.signal.aborted) { setStatus(cloud); setTransport("cloud"); setChecking(false) }
          return
        }
        cloudError = cloud.capabilities.find((item) => item.id === "chat")?.detail || "IA hospedada não configurada."
      } catch (reason) { cloudError = reason instanceof Error ? reason.message : "IA hospedada indisponível." }
      if (controller.signal.aborted) return
      try {
        const local = parseChatStatus(await chatRequest("local", "status", {}, controller.signal))
        if (!controller.signal.aborted) { setStatus(local); setTransport("local"); setConnectionError("") }
      } catch (reason) {
        if (!controller.signal.aborted) { setTransport("local"); setConnectionError(`${reason instanceof Error ? reason.message : "Serviço local indisponível."} ${cloudError}`) }
      } finally { if (!controller.signal.aborted) setChecking(false) }
    }
    void discover()
    return () => {
      mountedRef.current = false
      controller.abort()
      abortRef.current?.abort()
      statusAbortRef.current?.abort()
      if (recordTimerRef.current) clearTimeout(recordTimerRef.current)
      if (recorderRef.current?.state === "recording") recorderRef.current.stop()
      streamRef.current?.getTracks().forEach((track) => track.stop())
      window.speechSynthesis?.cancel()
    }
  }, [])

  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])

  function updateConversations(update: (current: Conversation[]) => Conversation[]) {
    setConversations((current) => {
      const next = update(current).sort((left, right) => right.updatedAt - left.updatedAt)
      writeHistory(storageKey, next)
      conversationsRef.current = next
      return next
    })
  }

  function appendMessage(conversationId: string, message: Message, title?: string) {
    updateConversations((current) => {
      const existing = current.find((item) => item.id === conversationId)
      const conversation = existing ?? { id: conversationId, title: title ?? "Nova conversa", updatedAt: Date.now(), messages: [] }
      return [{ ...conversation, updatedAt: Date.now(), messages: [...conversation.messages, message] }, ...current.filter((item) => item.id !== conversationId)]
    })
  }

  function patchMessage(conversationId: string, messageId: string, patch: Partial<Message>, persist = false) {
    setConversations((current) => {
      const next = current.map((conversation) => conversation.id !== conversationId ? conversation : {
        ...conversation, messages: conversation.messages.map((message) => message.id === messageId ? { ...message, ...patch } : message) })
      conversationsRef.current = next
      if (persist) writeHistory(storageKey, next)
      return next
    })
  }

  function removeMessage(conversationId: string, messageId: string) {
    setConversations((current) => {
      const next = current.map((conversation) => conversation.id !== conversationId ? conversation : {
        ...conversation, messages: conversation.messages.filter((message) => message.id !== messageId) })
      conversationsRef.current = next
      writeHistory(storageKey, next)
      return next
    })
  }

  async function addFiles(list: FileList | File[] | null) {
    const files = Array.from(list ?? []).slice(0, Math.max(0, 4 - attachments.length))
    if (!files.length) return
    setError("")
    try {
      const prepared = await Promise.all(files.map(prepareAttachment))
      const total = [...attachments, ...prepared].reduce((sum, file) => sum + file.data_base64.length, 0)
      if (total > 4_100_000) throw new Error("Os anexos passam de 3 MB no total. Remova algum arquivo.")
      setAttachments((current) => [...current, ...prepared].slice(0, 4))
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não consegui anexar o arquivo.") }
  }

  function newConversation() {
    if (busy || recording) return
    stopSpeech(); setActiveId(""); setDraft(""); setError(""); setNotice(""); setMode("chat")
    draftRef.current?.focus()
  }

  function deleteConversation(id: string) {
    updateConversations((current) => current.filter((item) => item.id !== id))
    if (id === activeId) setActiveId("")
  }

  async function refreshConnection(next: ChatTransport = transport) {
    statusAbortRef.current?.abort()
    const controller = new AbortController()
    statusAbortRef.current = controller
    setTransport(next); setChecking(true); setConnectionError(""); setStatus(null)
    try {
      const value = parseChatStatus(await chatRequest(next, "status", {}, controller.signal))
      if (!controller.signal.aborted) setStatus(value)
    } catch (reason) { if (!controller.signal.aborted) setConnectionError(reason instanceof Error ? reason.message : "Não foi possível verificar a conexão.") }
    finally { if (!controller.signal.aborted) setChecking(false) }
  }

  type ChatRun = { conversationId: string; history: Message[]; sentFiles?: ChatAttachment[]; userMessage?: Message; continueId?: string; onFail?: () => void }

  /** One chat answer: a new reply, or the continuation of `continueId`. Streams in the cloud; classic request otherwise. */
  async function runChat({ conversationId, history, sentFiles = [], userMessage, continueId, onFail }: ChatRun) {
    setBusy(true); setError(""); setNotice("")
    const controller = new AbortController()
    abortRef.current = controller
    const files = sentFiles.length ? { attachments: sentFiles.map(({ name, mime, data_base64 }) => ({ name, mime, data_base64 })) } : {}
    const photoBudget = 3_600_000 - sentFiles.reduce((sum, file) => sum + file.data_base64.length, 0)
    const base = boundedHistory(history, photosRef.current, photoBudget)
    const chatHistory: ChatMessage[] = continueId ? [...base, { role: "user", content: "Continue exatamente de onde a sua última resposta parou. Não repita nada do que já escreveu e não comente que está continuando." }] : base
    const sentPhotos = sentFiles.filter((file) => file.kind === "image").map(({ name, mime, data_base64 }) => ({ name, mime, data_base64 }))
    // What was attached stays with this message for the next questions: the photos while the page is open, the documents' text in the history.
    const remember = (fileContext?: string) => {
      if (!userMessage) return
      if (sentPhotos.length) photosRef.current.set(userMessage.id, sentPhotos)
      if (fileContext) patchMessage(conversationId, userMessage.id, { file_context: fileContext })
    }
    const previous = continueId ? history.find((message) => message.id === continueId)?.content ?? "" : ""
    const show = (text: string) => continueId ? joinContinuation(previous, text) : text
    let shown = ""

    const classic = async () => {
      const reply = parseChatReply(await chatRequest(transport, "chat", { messages: chatHistory, ...files }, controller.signal))
      const image = reply.image ? { ...reply.image, thumb: await imageThumbnail(reply.image.src) } : undefined
      if (controller.signal.aborted) return
      remember(reply.file_context)
      openFirst(reply.actions)
      if (continueId) patchMessage(conversationId, continueId, { content: show(reply.text), interrupted: false, streaming: false }, true)
      else appendMessage(conversationId, { id: crypto.randomUUID(), role: "assistant", content: reply.text, video: reply.video, image, sources: reply.sources, actions: reply.actions })
    }

    // The answer appears while it is written; the classic request stays as the fallback.
    const streamed = async () => {
      const replyId = continueId ?? crypto.randomUUID()
      if (continueId) patchMessage(conversationId, replyId, { streaming: true, interrupted: false, status: undefined })
      else appendMessage(conversationId, { id: replyId, role: "assistant", content: "", streaming: true })
      try {
        const reply = await streamChat({ messages: chatHistory, ...files }, (event) => {
          if (event.type === "delta") { shown += event.text; patchMessage(conversationId, replyId, { content: show(shown), status: undefined }) }
          else if (event.type === "reset") { shown = ""; patchMessage(conversationId, replyId, { content: show("") }) }
          else patchMessage(conversationId, replyId, { status: event.text })
        }, controller.signal)
        const image = reply.image ? { ...reply.image, thumb: await imageThumbnail(reply.image.src) } : undefined
        remember(reply.file_context)
        openFirst(reply.actions)
        patchMessage(conversationId, replyId, { content: show(reply.text), image, video: reply.video, ...(reply.sources ? { sources: reply.sources } : {}), ...(reply.actions ? { actions: reply.actions } : {}), streaming: false, status: undefined }, true)
      } catch (reason) {
        if (reason instanceof StreamUnavailableError && !shown) {
          if (continueId) patchMessage(conversationId, replyId, { streaming: false, status: undefined })
          else removeMessage(conversationId, replyId)
          return classic()
        }
        // What already appeared stays; "Continuar" finishes it.
        if (shown || continueId) patchMessage(conversationId, replyId, { content: show(shown), streaming: false, status: undefined, interrupted: true }, true)
        else removeMessage(conversationId, replyId)
        throw reason
      }
    }

    try {
      await (transport === "cloud" ? streamed() : classic())
    } catch (reason) {
      if (controller.signal.aborted) setNotice(shown || continueId ? "Resposta interrompida. Toque em “Continuar” para a Kiara terminar." : "Resposta interrompida.")
      else { setError(reason instanceof Error ? reason.message : "Não foi possível concluir a resposta."); onFail?.() }
    } finally { setBusy(false); abortRef.current = null }
  }

  async function send() {
    const sentFiles = mode === "chat" ? attachments : []
    const content = draft.trim() || (sentFiles.length ? "Analise o que eu anexei." : "")
    if (!content || busy || recording || !available) return
    const conversationId = activeId || crypto.randomUUID()
    const editing = editingId ? messages.find((message) => message.id === editingId) : undefined
    const base = editing ? messages.slice(0, messages.indexOf(editing)) : messages
    // An edited question keeps what was attached to it unless new files were chosen.
    const kept: Partial<Message> = !sentFiles.length && editing?.files?.length ? { files: editing.files, ...(editing.file_context ? { file_context: editing.file_context } : {}) } : {}
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content,
      ...(sentFiles.length ? { files: sentFiles.map(({ name, kind, preview }) => ({ name, kind, preview })) } : kept) }
    if (editing) {
      const photos = photosRef.current.get(editing.id)
      if (photos && kept.files) photosRef.current.set(userMessage.id, photos)
      // Editing the first question also renames the conversation.
      const title = base.some((message) => message.role === "user") ? undefined : content.replace(/\s+/g, " ").slice(0, 60)
      updateConversations((current) => current.map((conversation) => conversation.id === conversationId ? { ...conversation, messages: base, ...(title ? { title } : {}) } : conversation))
    }
    // The files go as attachments now; the note "[anexos enviados…]" only marks them in later turns.
    const history = [...base, sentFiles.length ? { ...userMessage, files: undefined } : userMessage]
    setActiveId(conversationId); setEditingId("")
    appendMessage(conversationId, userMessage, content.replace(/\s+/g, " ").slice(0, 60))
    setDraft(""); setAttachments([])
    if (mode === "chat") return runChat({ conversationId, history, sentFiles, userMessage, onFail: () => { setDraft(content); setAttachments(sentFiles) } })

    setBusy(true); setError(""); setNotice("")
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const action = mode === "website" || mode === "dashboard" ? "build" : mode === "automation" ? "plan" : mode
      const body = action === "build" ? { prompt: content, kind: mode } : mode === "video" ? { action: "start", prompt: content } : { prompt: content }
      const reply = parseChatReply(await chatRequest(transport, action, body, controller.signal))
      const image = reply.image ? { ...reply.image, thumb: await imageThumbnail(reply.image.src) } : undefined
      if (!controller.signal.aborted) appendMessage(conversationId, { id: crypto.randomUUID(), role: "assistant", content: reply.text, artifact: reply.artifact, plan: reply.plan, video: reply.video, image, sources: reply.sources, actions: reply.actions })
    } catch (reason) {
      if (controller.signal.aborted) setNotice("Geração interrompida. A solicitação pode já ter sido recebida pelo serviço.")
      else { setError(reason instanceof Error ? reason.message : "Não foi possível concluir a resposta."); setDraft(content) }
    } finally { setBusy(false); abortRef.current = null }
  }

  /** Asks the last question again: the last answer is replaced. */
  function retry() {
    if (busy || !active || !available) return
    const index = messages.findLastIndex((message) => message.role === "user")
    if (index < 0) return
    const base = messages.slice(0, index + 1)
    updateConversations((current) => current.map((conversation) => conversation.id === active.id ? { ...conversation, messages: base, updatedAt: Date.now() } : conversation))
    void runChat({ conversationId: active.id, history: base })
  }

  function continueAnswer(message: Message) {
    if (busy || !active || !available) return
    void runChat({ conversationId: active.id, history: messages, continueId: message.id })
  }

  function editMessage(message: Message) {
    if (busy) return
    setEditingId(message.id); setMode("chat"); setDraft(message.content); setAttachments([]); setError(""); setNotice("")
    requestAnimationFrame(() => { const element = draftRef.current; if (element) { element.focus(); element.style.height = "auto"; element.style.height = `${Math.min(element.scrollHeight, 208)}px` } })
  }

  function openFile(file: SentFile, message?: Message) {
    const photos = message ? photosRef.current.get(message.id) : undefined
    const attachment = !message ? attachments.find((item) => item.name === file.name) : undefined
    const photo = photos?.find((item) => item.name === file.name) ?? attachment
    if (file.kind === "image") return setPreview({ name: file.name, kind: file.kind, image: photo ? `data:${photo.mime};base64,${photo.data_base64}` : file.preview })
    const text = fileSection(message?.file_context, file.name)
    const sheets = [...text.matchAll(/^\[aba "([^"]+)": (\d+) linha/gm)].map((match) => `${match[1]} (${match[2]} linha${match[2] === "1" ? "" : "s"})`)
    setPreview({ name: file.name, kind: file.kind, text, sheets, pending: !message })
  }

  async function share(message: Message, how: "whatsapp-copy" | "whatsapp-send" | "word" | "pdf") {
    try {
      if (how === "word") return downloadWord(message.content)
      if (how === "pdf") return printAnswer(message.content)
      const text = whatsappText(message.content)
      if (how === "whatsapp-send") return void window.open(`https://wa.me/?text=${encodeURIComponent(text.slice(0, 6000))}`, "_blank", "noopener,noreferrer")
      await navigator.clipboard.writeText(text)
      setNotice("Copiado no formato do WhatsApp: é só colar na conversa.")
    } catch { setError("Não foi possível exportar a resposta.") }
  }

  function togglePin(id: string) {
    setConversations((current) => {
      const next = current.map((conversation) => conversation.id === id ? { ...conversation, pinned: !conversation.pinned } : conversation)
      conversationsRef.current = next
      writeHistory(storageKey, next)
      return next
    })
  }

  async function transcribe(file: File) {
    if (busy || !canTranscribe) return
    try {
      const mime = validateChatAudio(file)
      setBusy(true); setError(""); setNotice("Transcrevendo seu áudio…")
      const controller = new AbortController()
      abortRef.current = controller
      const payload = await chatRequest(transport, "transcribe", { audio_base64: await blobBase64(file), mime, filename: file.name }, controller.signal) as { text?: unknown }
      if (controller.signal.aborted) return
      if (typeof payload?.text !== "string" || !payload.text.trim()) throw new Error("Não foi encontrada uma transcrição válida neste áudio.")
      setDraft((current) => `${current}${current ? "\n" : ""}${payload.text}`.slice(0, 10_000))
      setNotice("Áudio transcrito. Revise o texto e envie.")
      draftRef.current?.focus()
    } catch (reason) { if (!(reason instanceof DOMException && reason.name === "AbortError")) setError(reason instanceof Error ? reason.message : "Não foi possível transcrever o áudio.") }
    finally { setBusy(false); abortRef.current = null; if (fileRef.current) fileRef.current.value = "" }
  }

  async function startRecording() {
    if (recording) { recorderRef.current?.stop(); return }
    if (busy || !canTranscribe) return
    setError("")
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Este navegador não oferece gravação. Anexe um arquivo de áudio.")
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mountedRef.current) { stream.getTracks().forEach((track) => track.stop()); return }
      streamRef.current = stream
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      recorderRef.current = recorder
      chunksRef.current = []
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        if (recordTimerRef.current) clearTimeout(recordTimerRef.current)
        if (!mountedRef.current) return
        setRecording(false)
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" })
        void transcribe(new File([blob], "gravacao-kiara.webm", { type: blob.type }))
      }
      recorder.start(1000)
      setRecording(true); setNotice("Gravando… clique no quadrado para parar (até 60 segundos).")
      recordTimerRef.current = setTimeout(() => { if (recorder.state === "recording") recorder.stop() }, 60_000)
    } catch (reason) { streamRef.current?.getTracks().forEach((track) => track.stop()); setError(reason instanceof Error ? reason.message : "Não foi possível acessar o microfone.") }
  }

  function stopSpeech() {
    window.speechSynthesis?.cancel()
    audioRef.current?.pause()
    setSpeaking(false)
  }

  async function speak(text: string) {
    stopSpeech(); setError("")
    try {
      if (capability("speech")?.available) {
        setSpeaking(true)
        const payload = await chatRequest(transport, "speech", { text: text.slice(0, 5000) }) as { audio_base64?: unknown; mime?: unknown }
        if (typeof payload.audio_base64 !== "string" || typeof payload.mime !== "string" || !payload.mime.startsWith("audio/") || payload.audio_base64.length > 15_000_000) throw new Error("A voz não retornou um áudio válido.")
        const binary = atob(payload.audio_base64)
        const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
        setAudioUrl(URL.createObjectURL(new Blob([bytes], { type: payload.mime })))
        setSpeaking(false)
      } else {
        if (!browserVoice) throw new Error("Voz indisponível neste navegador.")
        const utterance = new SpeechSynthesisUtterance(text.slice(0, 5000))
        utterance.lang = "pt-BR"
        const voice = femininePortugueseVoice()
        if (voice) utterance.voice = voice
        utterance.onend = () => setSpeaking(false)
        utterance.onerror = () => { setSpeaking(false); setError("A leitura de voz foi interrompida ou não está disponível.") }
        setSpeaking(true)
        window.speechSynthesis.speak(utterance)
      }
    } catch (reason) { setSpeaking(false); setError(reason instanceof Error ? reason.message : "Não foi possível gerar a voz.") }
  }

  /** One spoken turn: same conversation history as the written chat. */
  async function askByVoice(content: string): Promise<string> {
    const conversationId = activeIdRef.current || crypto.randomUUID()
    const previous = conversationsRef.current.find((item) => item.id === conversationId)?.messages ?? []
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content }
    activeIdRef.current = conversationId
    setActiveId(conversationId)
    appendMessage(conversationId, userMessage, content.replace(/\s+/g, " ").slice(0, 60))
    // Voice turns ask for a short spoken answer from a fast model (the local bridge ignores the flag).
    const reply = parseChatReply(await chatRequest(transport, "chat", { messages: boundedHistory([...previous, userMessage]), ...(transport === "cloud" ? { voice: true } : {}) }))
    appendMessage(conversationId, { id: crypto.randomUUID(), role: "assistant", content: reply.text })
    return reply.text
  }

  const voiceBackends: VoiceBackends = {
    ask: askByVoice,
    synthesize: capability("speech")?.available ? async (text) => {
      const payload = await chatRequest(transport, "speech", { text: text.slice(0, 5000) }) as { audio_base64?: unknown; mime?: unknown }
      if (typeof payload.audio_base64 !== "string" || typeof payload.mime !== "string" || !payload.mime.startsWith("audio/") || payload.audio_base64.length > 15_000_000) throw new Error("Voz inválida.")
      return new Blob([Uint8Array.from(atob(payload.audio_base64), (char) => char.charCodeAt(0))], { type: payload.mime })
    } : undefined,
    transcribe: canTranscribe ? async (audio) => {
      const mime = audio.type.split(";", 1)[0] || "audio/webm"
      const payload = await chatRequest(transport, "transcribe", { audio_base64: await blobBase64(audio), mime, filename: "voz-kiara.webm" }) as { text?: unknown }
      return typeof payload?.text === "string" ? payload.text : ""
    } : undefined,
  }
  const voiceReady = Boolean(status?.connected && capability("chat")?.available)
  const canAttach = mode === "chat" && transport === "cloud" && Boolean(status?.connected)

  async function copy(message: Message) {
    try { await navigator.clipboard.writeText(message.role === "assistant" ? plainText(message.content) : message.content); setCopied(message.id); setTimeout(() => setCopied(""), 1500) } catch { setError("Não foi possível copiar.") }
  }

  const statusLabel = checking ? "Verificando…" : status?.connected ? (status.model || (transport === "local" ? "Neste computador" : "IA hospedada")) : "IA desconectada"
  const composer = <div className="w-full">
    <div className="rounded-3xl border bg-card px-3 pb-2 pt-3 shadow-sm focus-within:border-primary/40">
      {editingId ? <div className="mb-2 flex items-center gap-2 rounded-xl bg-primary/10 px-3 py-1.5 text-xs text-primary"><Pencil className="size-3.5 shrink-0" aria-hidden="true" /><span className="flex-1">Editando sua pergunta. Ao enviar, a conversa continua a partir dela.</span><button type="button" onClick={() => { setEditingId(""); setDraft("") }} className="font-medium underline-offset-2 hover:underline">Cancelar</button></div> : null}
      {attachments.length ? <div className="mb-2 flex flex-wrap gap-2">{attachments.map((file, index) => <AttachmentChip key={`${file.name}-${index}`} file={file} onOpen={() => openFile(file)}
        onRemove={() => setAttachments((current) => current.filter((_, position) => position !== index))} />)}</div> : null}
      <label className="sr-only" htmlFor="kiara-chat-message">Sua mensagem para a Kiara</label>
      <textarea ref={draftRef} id="kiara-chat-message" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={10_000} rows={1} placeholder={activeMode.placeholder} disabled={busy || recording}
        onInput={(event) => { const element = event.currentTarget; element.style.height = "auto"; element.style.height = `${Math.min(element.scrollHeight, 208)}px` }}
        onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } else if (event.key === "Escape" && editingId) { setEditingId(""); setDraft("") } }}
        onPaste={(event) => { const images = Array.from(event.clipboardData.files); if (images.length && canAttach) { event.preventDefault(); void addFiles(images) } }}
        className="max-h-52 min-h-7 w-full resize-none bg-transparent px-1 text-[15px] leading-6 outline-none placeholder:text-muted-foreground" />
      <div className="mt-2 flex items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button type="button" variant="ghost" size="sm" className="h-8 gap-1.5 rounded-full px-2.5 text-muted-foreground" disabled={busy || recording} aria-label={`Modo: ${activeMode.label}`}><Plus className="size-4" /><activeMode.icon className="size-4" /><span className="hidden sm:inline">{activeMode.label}</span></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-52">
            <DropdownMenuLabel>O que você quer fazer?</DropdownMenuLabel>
            {modes.map(({ id, label, icon: Icon }) => <DropdownMenuItem key={id} onSelect={() => setMode(id)}><Icon />{label}{mode === id ? <Check className="ml-auto" /> : null}</DropdownMenuItem>)}
          </DropdownMenuContent>
        </DropdownMenu>
        <input ref={fileRef} className="sr-only" type="file" accept="audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/flac" onChange={(event) => { const file = event.target.files?.[0]; if (file) void transcribe(file) }} aria-label="Arquivo de áudio para transcrever" tabIndex={-1} />
        <input ref={attachRef} className="sr-only" type="file" multiple accept={CHAT_ATTACHMENT_ACCEPT} onChange={(event) => { void addFiles(event.target.files); event.target.value = "" }} aria-label="Escolher arquivos para anexar" tabIndex={-1} />
        <Button type="button" variant="ghost" size="icon" className="size-8 rounded-full text-muted-foreground" onClick={() => (canAttach ? attachRef : fileRef).current?.click()} disabled={busy || recording || (!canAttach && !canTranscribe) || attachments.length >= 4} aria-label={canAttach ? "Anexar arquivo" : "Anexar áudio"} title={canAttach ? "Anexar fotos, PDF, Word, planilhas ou texto (até 3 MB no total)" : canTranscribe ? "Anexar áudio de até 5 MB" : "Anexos indisponíveis nesta conexão"}><Paperclip /></Button>
        <Button type="button" variant="ghost" size="icon" className={cn("size-8 rounded-full text-muted-foreground", recording && "bg-destructive/15 text-destructive")} onClick={() => void startRecording()} disabled={busy || !canTranscribe} aria-label={recording ? "Parar gravação" : "Gravar áudio"} aria-pressed={recording}>{recording ? <Square /> : <Mic />}</Button>
        <div className="ml-auto">
          {busy ? <Button type="button" size="icon" className="size-9 rounded-full" onClick={() => abortRef.current?.abort()} aria-label="Parar resposta" title="Parar resposta (o que já foi escrito fica)"><Square className="fill-current" /></Button>
            : !draft.trim() && !attachments.length && !recording ? <Button type="button" size="icon" className="size-9 rounded-full" onClick={() => { stopSpeech(); setVoiceOpen(true) }} disabled={!voiceReady || checking} aria-label="Conversar por voz" title={voiceReady ? "Conversar por voz" : "Conecte a IA para conversar por voz"}><AudioLines /></Button>
            : <Button type="button" size="icon" className="size-9 rounded-full" onClick={() => void send()} disabled={(!draft.trim() && !attachments.length) || !available || checking || recording} aria-label={mode === "automation" ? "Preparar plano" : "Enviar"}><ArrowUp /></Button>}
        </div>
      </div>
    </div>
    {!checking && !available ? <p className="mt-2 px-3 text-center text-xs text-muted-foreground">{!isAdmin ? status?.connected ? `${activeMode.label} ainda não está disponível.` : "A Kiara está indisponível no momento. Tente novamente em instantes."
      : status?.connected ? capability(mode)?.detail || `${activeMode.label} ainda não está disponível nesta conexão.` : "A IA não está conectada. Abra os ajustes para verificar a conexão."}</p> : null}
    {error ? <p role="alert" className="mt-2 px-3 text-center text-sm text-destructive">{error}</p> : notice ? <p role="status" className="mt-2 px-3 text-center text-xs text-muted-foreground">{notice}</p> : null}
  </div>

  return <ImmersiveShell
    label="Conversas da Kiara"
    sidebar={(close) => <nav aria-label="Histórico de conversas" className="space-y-4">
      <Button type="button" variant="ghost" className="w-full justify-start gap-2 px-2" onClick={() => { newConversation(); close() }} disabled={busy || recording}><Plus />Nova conversa</Button>
      {conversations.length ? (() => {
        const words = fold(query).split(/\s+/).filter(Boolean)
        const found = words.length ? conversations.filter((conversation) => { const haystack = fold(conversation.title + " " + conversation.messages.map((message) => message.content).join(" ")); return words.every((word) => haystack.includes(word)) }) : conversations
        const row = (conversation: Conversation) => <li key={conversation.id} className="group relative">
          <button type="button" onClick={() => { setActiveId(conversation.id); setEditingId(""); setError(""); setNotice(""); close() }} aria-current={conversation.id === activeId ? "true" : undefined} disabled={busy}
            className={cn("block w-full truncate rounded-lg px-2 py-2 pr-16 text-left text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-foreground/5", conversation.id === activeId && "bg-sidebar-foreground/10 text-sidebar-foreground")}>{conversation.title}</button>
          <span className="absolute right-1 top-1/2 flex -translate-y-1/2 opacity-0 focus-within:opacity-100 group-hover:opacity-100 max-md:opacity-100">
            <button type="button" onClick={() => togglePin(conversation.id)} aria-label={conversation.pinned ? `Desafixar ${conversation.title}` : `Fixar ${conversation.title}`} title={conversation.pinned ? "Desafixar" : "Fixar no topo"} className="grid size-7 place-items-center rounded-md text-sidebar-foreground/50 hover:text-sidebar-foreground">{conversation.pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}</button>
            <button type="button" onClick={() => deleteConversation(conversation.id)} disabled={busy} aria-label={`Excluir ${conversation.title}`} title="Excluir" className="grid size-7 place-items-center rounded-md text-sidebar-foreground/50 hover:text-destructive"><Trash2 className="size-3.5" /></button>
          </span>
        </li>
        const pinned = found.filter((conversation) => conversation.pinned)
        const recent = found.filter((conversation) => !conversation.pinned)
        return <div className="space-y-4">
          <label className="relative block"><span className="sr-only">Buscar nas conversas</span><Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-sidebar-foreground/45" aria-hidden="true" />
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar nas conversas" className="h-9 w-full rounded-lg border border-sidebar-border bg-transparent pl-8 pr-2 text-sm outline-none placeholder:text-sidebar-foreground/45 focus:border-primary/50" /></label>
          {pinned.length ? <div><p className="flex items-center gap-1 px-2 pb-1 text-xs font-medium text-sidebar-foreground/50"><Pin className="size-3" aria-hidden="true" />Fixadas</p><ul className="space-y-0.5">{pinned.map(row)}</ul></div> : null}
          {recent.length ? <div><p className="px-2 pb-1 text-xs font-medium text-sidebar-foreground/50">{words.length ? "Resultados" : "Recentes"}</p><ul className="space-y-0.5">{recent.map(row)}</ul></div> : null}
          {!found.length ? <p className="px-2 text-xs text-sidebar-foreground/50">Nenhuma conversa com “{query.trim()}”.</p> : null}
        </div>
      })() : <p className="px-2 text-xs text-sidebar-foreground/50">Suas conversas aparecem aqui. Elas ficam salvas apenas neste navegador.</p>}
    </nav>}
    footer={isAdmin ? <button type="button" onClick={() => setSettingsOpen(true)} className="flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground"><Settings2 className="size-4" aria-hidden="true" />Ajustes e recursos</button> : undefined}
    topBar={<>
      <span className="truncate font-medium">KIARA Chat</span>
      {isAdmin ? <>
        <span className="ml-auto inline-flex items-center gap-1.5 truncate text-xs text-muted-foreground" role="status"><span className={cn("size-1.5 shrink-0 rounded-full", checking ? "bg-amber-400" : status?.connected ? "bg-emerald-400" : "bg-muted-foreground")} aria-hidden="true" />{statusLabel}</span>
        <Button type="button" variant="ghost" size="icon" aria-label="Ajustes e recursos" onClick={() => setSettingsOpen(true)}><Settings2 /></Button>
      </> : null}
    </>}
  >
    <div className="relative flex min-h-0 flex-1 flex-col"
      onDragEnter={(event) => { if (!canAttach || !event.dataTransfer.types.includes("Files")) return; event.preventDefault(); dragDepth.current += 1; setDragging(true) }}
      onDragOver={(event) => { if (canAttach && event.dataTransfer.types.includes("Files")) { event.preventDefault(); event.dataTransfer.dropEffect = "copy" } }}
      onDragLeave={() => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setDragging(false) }}
      onDrop={(event) => { if (!canAttach) return; event.preventDefault(); dragDepth.current = 0; setDragging(false); if (!busy) void addFiles(event.dataTransfer.files) }}>
    {dragging ? <div className="pointer-events-none absolute inset-3 z-30 grid place-items-center rounded-3xl border-2 border-dashed border-primary/60 bg-background/85 backdrop-blur-sm fx-rise" aria-hidden="true">
      <div className="text-center"><Upload className="mx-auto mb-3 size-8 text-primary" /><p className="font-medium">Solte para anexar</p><p className="mt-1 text-sm text-muted-foreground">Fotos, PDF, Word, planilhas ou texto · até 4 arquivos</p></div>
    </div> : null}
    {messages.length ? <>
      <div className="min-h-0 flex-1 overflow-y-auto" role="log" aria-label="Mensagens da conversa" aria-live="polite" aria-relevant="additions">
        <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-8">
          {messages.map((message, index) => message.role === "user"
            ? <div key={message.id} className={cn("group/user flex flex-col items-end gap-1.5", index >= messages.length - 2 && "fx-rise")}>
              {message.files?.length ? <div className="flex max-w-[85%] flex-wrap justify-end gap-1.5">{message.files.map((file, position) => <AttachmentChip key={position} file={file} onOpen={() => openFile(file, message)} />)}</div> : null}
              <div className={cn("max-w-[85%] whitespace-pre-wrap break-words rounded-3xl bg-muted px-4 py-2.5 text-[15px] leading-6", editingId === message.id && "ring-2 ring-primary/50")}>{message.content}</div>
              <div className="flex gap-0.5 text-muted-foreground opacity-0 transition-opacity focus-within:opacity-100 group-hover/user:opacity-100 max-md:opacity-100">
                <Button type="button" variant="ghost" size="icon" className="size-7" onClick={() => void copy(message)} aria-label="Copiar pergunta">{copied === message.id ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}</Button>
                <Button type="button" variant="ghost" size="icon" className="size-7" onClick={() => editMessage(message)} disabled={busy} aria-label="Editar pergunta" title="Editar e enviar de novo"><Pencil className="size-3.5" /></Button>
              </div></div>
            : <article key={message.id} className={cn("flex gap-3", index >= messages.length - 2 && "fx-rise")} aria-label="Resposta da Kiara">
              <span className="grid size-7 shrink-0 place-items-center rounded-full border bg-card text-primary"><Bot className="size-4" aria-hidden="true" /></span>
              <div className="min-w-0 flex-1">
                {message.content ? <KiaraText text={message.content} /> : message.streaming ? <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status"><span className="kiara-thinking" aria-hidden="true"><i /><i /><i /></span>{message.status || "Pensando…"}</div> : null}
                {message.image && <Picture image={message.image} />}
                {message.artifact && <Artifact artifact={message.artifact} />}
                {message.video && <VideoJob key={message.video.id} initial={message.video} transport={transport} />}
                {message.plan && <section className="mt-3 rounded-2xl border p-4"><p className="flex items-center gap-2 text-sm font-medium"><Workflow className="size-4 text-primary" aria-hidden="true" />Plano para revisão</p><ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{message.plan.steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol><p className="mt-3 text-xs text-muted-foreground">Ainda não executado. Ações na máquina dependem de um executor autorizado.</p></section>}
                {message.actions?.length ? <div className="mt-2.5 flex flex-wrap gap-2">{message.actions.map((action) => <a key={action.url} href={action.url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3.5 text-sm font-medium text-foreground transition hover:bg-primary/20"><ExternalLink className="size-3.5 text-primary" />Abrir {action.label}</a>)}</div> : null}
                {message.sources?.length ? <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground"><span>Fontes:</span>{message.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" title={source.title} className="rounded-full border px-2 py-0.5 hover:bg-muted hover:text-foreground">{source.site}</a>)}</div> : null}
                {message.interrupted && !message.streaming ? <p className="mt-2 text-xs text-muted-foreground">Resposta interrompida.</p> : null}
                {!message.streaming && message.content ? <div className="mt-1 flex flex-wrap items-center gap-0.5 text-muted-foreground">
                  <Button type="button" variant="ghost" size="icon" className="size-8" onClick={() => void copy(message)} aria-label="Copiar resposta" title="Copiar">{copied === message.id ? <Check /> : <Copy />}</Button>
                  <Button type="button" variant="ghost" size="icon" className="size-8" onClick={() => void speak(plainText(message.content))} disabled={speaking || busy} aria-label="Ouvir resposta" title="Ouvir"><Volume2 /></Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild><Button type="button" variant="ghost" size="icon" className="size-8" aria-label="Exportar ou compartilhar" title="Exportar ou compartilhar"><Share2 /></Button></DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-56">
                      <DropdownMenuItem onSelect={() => void share(message, "whatsapp-copy")}><Copy />Copiar para o WhatsApp</DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => void share(message, "whatsapp-send")}><Share2 />Enviar pelo WhatsApp</DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => void share(message, "word")}><FileDown />Baixar em Word</DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => void share(message, "pdf")}><Download />Salvar em PDF</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  {index === messages.length - 1 && !message.artifact && !message.plan && !message.video ? <>
                    <Button type="button" variant="ghost" size="icon" className="size-8" onClick={retry} disabled={busy || !available} aria-label="Tentar de novo" title="Gerar outra resposta"><RotateCcw /></Button>
                    {message.interrupted || looksUnfinished(message.content) ? <Button type="button" variant="outline" size="sm" className="ml-1 h-8 gap-1 rounded-full" onClick={() => continueAnswer(message)} disabled={busy || !available}><ChevronsRight className="size-4" />Continuar</Button> : null}
                  </> : null}
                </div> : null}
              </div>
            </article>)}
          {busy && !messages.at(-1)?.streaming ? <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status"><span className="kiara-thinking" aria-hidden="true"><i /><i /><i /></span>{notice.startsWith("Transcrevendo") ? "Transcrevendo áudio…" : "Pensando…"}</div> : null}
          <div ref={endRef} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-4">
        {audioUrl || speaking ? <div className="mb-2 flex items-center gap-2">{audioUrl ? <audio ref={audioRef} controls src={audioUrl} onEnded={() => setSpeaking(false)} className="h-9 flex-1" /> : null}{speaking ? <Button type="button" size="sm" variant="outline" onClick={stopSpeech}><Square />Parar voz</Button> : null}</div> : null}
        {composer}
        <p className="mt-2 text-center text-[11px] text-muted-foreground">A Kiara pode errar. Revise respostas e arquivos antes de usar.</p>
      </div>
    </> : <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-10">
      <div className="w-full max-w-3xl">
        <span className="kiara-halo mx-auto mb-4 grid size-12 place-items-center rounded-full border bg-card text-primary"><Sparkles className="size-5" aria-hidden="true" /></span>
        <h1 className="mb-8 text-center text-2xl font-medium tracking-tight sm:text-3xl">Como posso ajudar hoje?</h1>
        {composer}
        <div className="mt-6 grid gap-2 sm:grid-cols-2">{suggestions.map((item) => <button key={item.title} type="button" onClick={() => { setMode(item.mode); setDraft(item.text); draftRef.current?.focus() }} style={{ "--i": suggestions.indexOf(item) } as React.CSSProperties} className="fx-rise fx-spot fx-tilt rounded-2xl border px-4 py-3 text-left hover:bg-muted/50" data-tilt="5"><p className="text-sm font-medium">{item.title}</p><p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{item.text}</p></button>)}</div>
      </div>
    </div>}
    </div>

    <Dialog open={Boolean(preview)} onOpenChange={(open) => { if (!open) setPreview(null) }}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader><DialogTitle className="truncate pr-6">{preview?.name}</DialogTitle>
          <DialogDescription>{preview?.kind === "image" ? "Foto anexada" : preview?.pending ? "Anexo pronto para enviar" : preview?.sheets?.length ? `Planilha com ${preview.sheets.length} aba${preview.sheets.length === 1 ? "" : "s"} lida${preview.sheets.length === 1 ? "" : "s"} pela Kiara` : "O que a Kiara leu deste arquivo"}</DialogDescription></DialogHeader>
        {/* eslint-disable-next-line @next/next/no-img-element -- local data URL */}
        {preview?.image ? <img src={preview.image} alt={preview.name} className="mx-auto max-h-[70dvh] w-auto rounded-xl object-contain" /> : null}
        {preview?.sheets?.length ? <div className="flex flex-wrap gap-1.5">{preview.sheets.map((sheet) => <span key={sheet} className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"><FileSpreadsheet className="size-3.5 text-primary" aria-hidden="true" />{sheet}</span>)}</div> : null}
        {preview && preview.kind !== "image" ? preview.text ? <pre className="max-h-[55dvh] overflow-auto whitespace-pre-wrap rounded-xl bg-muted p-3 text-xs leading-5">{preview.text.slice(0, 20_000)}</pre>
          : <p className="text-sm text-muted-foreground">{preview.pending ? "O conteúdo aparece aqui depois que a Kiara ler o arquivo." : "O texto deste arquivo não ficou guardado neste navegador."}</p> : null}
      </DialogContent>
    </Dialog>

    {voiceOpen ? <VoiceConversation backends={voiceBackends} onClose={() => setVoiceOpen(false)} /> : null}

    <Dialog open={isAdmin && settingsOpen} onOpenChange={setSettingsOpen}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader><DialogTitle>Ajustes e recursos</DialogTitle><DialogDescription>Conexão da inteligência e recursos disponíveis.</DialogDescription></DialogHeader>
        <div className="space-y-5">
          <div className="space-y-2">
            <label htmlFor="chat-transport" className="text-sm font-medium">Conexão</label>
            <div className="flex gap-2">
              <select id="chat-transport" value={transport} disabled={busy || recording || checking} onChange={(event) => void refreshConnection(event.target.value as ChatTransport)} className="h-10 flex-1 rounded-md border bg-background px-3 text-sm"><option value="cloud">IA hospedada</option><option value="local">Neste computador</option></select>
              <Button type="button" variant="outline" size="icon" className="size-10" aria-label="Verificar conexão" onClick={() => void refreshConnection()} disabled={checking || busy || recording}>{checking ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}</Button>
            </div>
            <p className="text-xs text-muted-foreground">{checking ? "Verificando…" : status?.connected ? `Conectado${status.model ? ` · ${status.model}` : ""}` : connectionError || "Não conectado."}</p>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium">Recursos</p>
            <ul className="divide-y rounded-xl border">{Object.entries(capabilityLabels).map(([id, label]) => { const item = capability(id); const ready = Boolean(item?.available && status?.connected); return <li key={id} className="flex items-start gap-3 px-3 py-2.5"><span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", ready ? "bg-emerald-400" : "bg-muted-foreground/50")} aria-hidden="true" /><div className="min-w-0"><p className="text-sm">{label}</p><p className="text-xs text-muted-foreground">{checking ? "Verificando…" : ready ? "Disponível" : item?.detail || "Não conectado"}</p></div></li> })}</ul>
          </div>
          <p className="flex items-start gap-2 text-xs text-muted-foreground"><AudioLines className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />{capability("speech")?.available ? "Voz da Kiara conectada." : browserVoice ? "Respostas lidas com a voz do navegador." : "Voz indisponível neste navegador."} O microfone só é usado quando você grava.</p>
          <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Usar a IA deste computador</summary><p className="mt-2">Inicie a ponte local com <code>python scripts/run_kiara_chat.py</code> e escolha “Neste computador”. O navegador pode pedir acesso à rede local.</p></details>
        </div>
      </DialogContent>
    </Dialog>
  </ImmersiveShell>
}
