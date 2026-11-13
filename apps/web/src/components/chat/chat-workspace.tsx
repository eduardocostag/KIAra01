"use client"

import { useEffect, useRef, useState, useSyncExternalStore } from "react"
import { ArrowUp, AudioLines, Bot, ChartNoAxesCombined, Check, Copy, Download, Globe2, ImagePlus, LoaderCircle, MessageCircle, Mic, Paperclip, Plus, RefreshCw, Settings2, Sparkles, Square, Trash2, Video, Volume2, Workflow } from "lucide-react"
import { ImmersiveShell } from "@/components/app-shell/immersive-shell"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { blobBase64, chatRequest, fetchVideo, isolatedHtml, parseChatReply, parseChatStatus, parseVideoJob, validateChatAudio, type ChatArtifact, type ChatVideoJob, type ChatMessage, type ChatMode, type ChatPlan, type ChatStatus, type ChatTransport } from "@/lib/chat-client"
import { cn } from "@/lib/utils"
import { pollVideoJob } from "@/lib/video-polling"
import { femininePortugueseVoice, VoiceConversation, type VoiceBackends } from "./voice-conversation"

type Message = ChatMessage & { id: string; artifact?: ChatArtifact; plan?: ChatPlan; video?: ChatVideoJob }
type Conversation = { id: string; title: string; updatedAt: number; messages: Message[] }

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
  { mode: "video" as const, title: "Vídeo de apresentação", text: "Crie um vídeo de apresentação da Kiara para Ana e Pedro, mostrando os módulos Leads e WhatsApp, com tom profissional e animado." },
  { mode: "automation" as const, title: "Planejar uma tarefa", text: "Prepare um plano revisável para organizar arquivos e automatizar tarefas recorrentes no computador." },
]
const HISTORY_LIMIT = 30

function boundedHistory(messages: Message[]): ChatMessage[] {
  let remaining = 35_000
  return messages.slice(-24).reverse().flatMap((message) => {
    if (remaining <= 0) return []
    const content = message.content.slice(0, Math.min(10_000, remaining))
    remaining -= content.length
    return [{ role: message.role, content }]
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
  const slim = conversations.slice(0, HISTORY_LIMIT).map((conversation) => ({ ...conversation, messages: conversation.messages.map(({ artifact, ...message }) => artifact ? { ...message, content: `${message.content}\n\n[Arquivo gerado: ${artifact.name}]` } : message) }))
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
    try { setUrl(URL.createObjectURL(await fetchVideo(job.id))) } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível abrir o vídeo.") }
  }
  const name = `kiara-video-${job.id.slice(0, 8)}.mp4`
  return <section className="mt-3 overflow-hidden rounded-2xl border" aria-label="Vídeo da Kiara">
    <div className="flex flex-wrap items-center gap-3 p-3">
      <Video className="size-5 text-primary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{job.title || "Vídeo de apresentação"}</p>
        <p className="text-xs text-muted-foreground" role="status">{job.status === "failed" ? job.error : job.status === "done" ? `Pronto${job.duration ? ` · ${Math.floor(job.duration / 60)}min${String(Math.round(job.duration % 60)).padStart(2, "0")}` : ""} · gerado neste computador` : job.message}</p>
      </div>
      {job.status === "done" && !url ? <Button type="button" size="sm" variant="outline" onClick={() => void load()}><Video aria-hidden="true" />Assistir</Button> : null}
      {pollPaused && job.status === "running" ? <Button type="button" size="sm" variant="outline" onClick={() => { setPollPaused(false); setError(""); setPollAttempt((attempt) => attempt + 1) }}><RefreshCw aria-hidden="true" />Retomar acompanhamento</Button> : null}
      {url ? <Button type="button" size="sm" variant="outline" asChild><a href={url} download={name}><Download aria-hidden="true" />Baixar</a></Button> : null}
    </div>
    {job.status === "running" ? <div className="h-1 bg-muted"><div className="h-full bg-primary transition-[width] duration-700" style={{ width: `${Math.max(3, job.progress * 100)}%` }} /></div> : null}
    {url ? <video className="aspect-video w-full border-t bg-black" src={url} controls autoPlay playsInline /> : null}
    {error ? <p className="border-t px-3 py-2 text-xs text-destructive">{error}</p> : null}
  </section>
}

const noop = () => () => {}

export function ChatWorkspace({ userId = "preview" }: { userId?: string }) {
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

  async function send() {
    const content = draft.trim()
    if (!content || busy || recording || !available) return
    const conversationId = activeId || crypto.randomUUID()
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content }
    const history = [...messages, userMessage]
    setActiveId(conversationId)
    appendMessage(conversationId, userMessage, content.replace(/\s+/g, " ").slice(0, 60))
    setDraft(""); setBusy(true); setError(""); setNotice("")
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const action = mode === "chat" ? "chat" : mode === "website" || mode === "dashboard" ? "build" : mode === "automation" ? "plan" : mode
      const body = mode === "chat" ? { messages: boundedHistory(history) } : action === "build" ? { prompt: content, kind: mode } : mode === "video" ? { action: "start", prompt: content } : { prompt: content }
      const reply = parseChatReply(await chatRequest(transport, action, body, controller.signal))
      if (!controller.signal.aborted) appendMessage(conversationId, { id: crypto.randomUUID(), role: "assistant", content: reply.text, artifact: reply.artifact, plan: reply.plan, video: reply.video })
    } catch (reason) {
      if (controller.signal.aborted) setNotice("Geração interrompida. A solicitação pode já ter sido recebida pelo serviço.")
      else { setError(reason instanceof Error ? reason.message : "Não foi possível concluir a resposta."); setDraft(content) }
    } finally { setBusy(false); abortRef.current = null }
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

  async function copy(message: Message) {
    try { await navigator.clipboard.writeText(message.content); setCopied(message.id); setTimeout(() => setCopied(""), 1500) } catch { setError("Não foi possível copiar.") }
  }

  const statusLabel = checking ? "Verificando…" : status?.connected ? (status.model || (transport === "local" ? "Neste computador" : "IA hospedada")) : "IA desconectada"
  const composer = <div className="w-full">
    <div className="rounded-3xl border bg-card px-3 pb-2 pt-3 shadow-sm focus-within:border-primary/40">
      <label className="sr-only" htmlFor="kiara-chat-message">Sua mensagem para a Kiara</label>
      <textarea ref={draftRef} id="kiara-chat-message" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={10_000} rows={1} placeholder={activeMode.placeholder} disabled={busy || recording}
        onInput={(event) => { const element = event.currentTarget; element.style.height = "auto"; element.style.height = `${Math.min(element.scrollHeight, 208)}px` }}
        onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } }}
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
        <Button type="button" variant="ghost" size="icon" className="size-8 rounded-full text-muted-foreground" onClick={() => fileRef.current?.click()} disabled={busy || recording || !canTranscribe} aria-label="Anexar áudio" title={canTranscribe ? "Anexar áudio de até 5 MB" : "Transcrição de áudio não conectada"}><Paperclip /></Button>
        <Button type="button" variant="ghost" size="icon" className={cn("size-8 rounded-full text-muted-foreground", recording && "bg-destructive/15 text-destructive")} onClick={() => void startRecording()} disabled={busy || !canTranscribe} aria-label={recording ? "Parar gravação" : "Gravar áudio"} aria-pressed={recording}>{recording ? <Square /> : <Mic />}</Button>
        <div className="ml-auto">
          {busy ? <Button type="button" size="icon" className="size-9 rounded-full" onClick={() => abortRef.current?.abort()} aria-label="Interromper"><Square className="fill-current" /></Button>
            : !draft.trim() && !recording ? <Button type="button" size="icon" className="size-9 rounded-full" onClick={() => { stopSpeech(); setVoiceOpen(true) }} disabled={!voiceReady || checking} aria-label="Conversar por voz" title={voiceReady ? "Conversar por voz" : "Conecte a IA para conversar por voz"}><AudioLines /></Button>
            : <Button type="button" size="icon" className="size-9 rounded-full" onClick={() => void send()} disabled={!draft.trim() || !available || checking || recording} aria-label={mode === "automation" ? "Preparar plano" : "Enviar"}><ArrowUp /></Button>}
        </div>
      </div>
    </div>
    {!checking && !available ? <p className="mt-2 px-3 text-center text-xs text-muted-foreground">{status?.connected ? capability(mode)?.detail || `${activeMode.label} ainda não está disponível nesta conexão.` : "A IA não está conectada. Abra os ajustes para verificar a conexão."}</p> : null}
    {error ? <p role="alert" className="mt-2 px-3 text-center text-sm text-destructive">{error}</p> : notice ? <p role="status" className="mt-2 px-3 text-center text-xs text-muted-foreground">{notice}</p> : null}
  </div>

  return <ImmersiveShell
    label="Conversas da Kiara"
    sidebar={(close) => <nav aria-label="Histórico de conversas" className="space-y-4">
      <Button type="button" variant="ghost" className="w-full justify-start gap-2 px-2" onClick={() => { newConversation(); close() }} disabled={busy || recording}><Plus />Nova conversa</Button>
      {conversations.length ? <div>
        <p className="px-2 pb-1 text-xs font-medium text-sidebar-foreground/50">Recentes</p>
        <ul className="space-y-0.5">{conversations.map((conversation) => <li key={conversation.id} className="group relative">
          <button type="button" onClick={() => { setActiveId(conversation.id); setError(""); setNotice(""); close() }} aria-current={conversation.id === activeId ? "true" : undefined} disabled={busy}
            className={cn("block w-full truncate rounded-lg px-2 py-2 pr-8 text-left text-sm text-sidebar-foreground/80 hover:bg-sidebar-foreground/5", conversation.id === activeId && "bg-sidebar-foreground/10 text-sidebar-foreground")}>{conversation.title}</button>
          <button type="button" onClick={() => deleteConversation(conversation.id)} disabled={busy} aria-label={`Excluir ${conversation.title}`} className="absolute right-1 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-sidebar-foreground/50 opacity-0 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"><Trash2 className="size-3.5" /></button>
        </li>)}</ul>
      </div> : <p className="px-2 text-xs text-sidebar-foreground/50">Suas conversas aparecem aqui. Elas ficam salvas apenas neste navegador.</p>}
    </nav>}
    footer={<button type="button" onClick={() => setSettingsOpen(true)} className="flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground"><Settings2 className="size-4" aria-hidden="true" />Ajustes e recursos</button>}
    topBar={<>
      <span className="truncate font-medium">KIARA Chat</span>
      <span className="ml-auto inline-flex items-center gap-1.5 truncate text-xs text-muted-foreground" role="status"><span className={cn("size-1.5 shrink-0 rounded-full", checking ? "bg-amber-400" : status?.connected ? "bg-emerald-400" : "bg-muted-foreground")} aria-hidden="true" />{statusLabel}</span>
      <Button type="button" variant="ghost" size="icon" aria-label="Ajustes e recursos" onClick={() => setSettingsOpen(true)}><Settings2 /></Button>
    </>}
  >
    {messages.length ? <>
      <div className="min-h-0 flex-1 overflow-y-auto" role="log" aria-label="Mensagens da conversa" aria-live="polite" aria-relevant="additions">
        <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-8">
          {messages.map((message, index) => message.role === "user"
            ? <div key={message.id} className={cn("flex justify-end", index >= messages.length - 2 && "fx-rise")}><div className="max-w-[85%] whitespace-pre-wrap break-words rounded-3xl bg-muted px-4 py-2.5 text-[15px] leading-6">{message.content}</div></div>
            : <article key={message.id} className={cn("flex gap-3", index >= messages.length - 2 && "fx-rise")} aria-label="Resposta da Kiara">
              <span className="grid size-7 shrink-0 place-items-center rounded-full border bg-card text-primary"><Bot className="size-4" aria-hidden="true" /></span>
              <div className="min-w-0 flex-1">
                <div className="whitespace-pre-wrap break-words text-[15px] leading-7">{message.content}</div>
                {message.artifact && <Artifact artifact={message.artifact} />}
                {message.video && <VideoJob key={message.video.id} initial={message.video} transport={transport} />}
                {message.plan && <section className="mt-3 rounded-2xl border p-4"><p className="flex items-center gap-2 text-sm font-medium"><Workflow className="size-4 text-primary" aria-hidden="true" />Plano para revisão</p><ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{message.plan.steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol><p className="mt-3 text-xs text-muted-foreground">Ainda não executado. Ações na máquina dependem de um executor autorizado.</p></section>}
                <div className="mt-1 flex gap-0.5 text-muted-foreground">
                  <Button type="button" variant="ghost" size="icon" className="size-8" onClick={() => void copy(message)} aria-label="Copiar resposta">{copied === message.id ? <Check /> : <Copy />}</Button>
                  <Button type="button" variant="ghost" size="icon" className="size-8" onClick={() => void speak(message.content)} disabled={speaking || busy} aria-label="Ouvir resposta"><Volume2 /></Button>
                </div>
              </div>
            </article>)}
          {busy ? <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status"><span className="kiara-thinking" aria-hidden="true"><i /><i /><i /></span>{notice.startsWith("Transcrevendo") ? "Transcrevendo áudio…" : "Pensando…"}</div> : null}
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

    {voiceOpen ? <VoiceConversation backends={voiceBackends} onClose={() => setVoiceOpen(false)} /> : null}

    <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
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
