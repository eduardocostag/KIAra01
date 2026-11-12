"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { AudioLines, Bot, ChartNoAxesCombined, Check, ChevronDown, CircleHelp, Download, FileAudio, Globe2, ImagePlus, LoaderCircle, MessageCircle, Mic, Paperclip, Plus, RefreshCw, Send, Settings2, ShieldCheck, Sparkles, Square, Video, Volume2, Workflow, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { blobBase64, chatRequest, isolatedHtml, parseChatReply, parseChatStatus, validateChatAudio, type ChatArtifact, type ChatMessage, type ChatMode, type ChatPlan, type ChatStatus, type ChatTransport } from "@/lib/chat-client"
import styles from "./chat.module.css"

type Message = ChatMessage & { id: string; artifact?: ChatArtifact; plan?: ChatPlan }
const modes = [
  { id: "chat", label: "Conversar", icon: MessageCircle, placeholder: "Converse com a Kiara, analise uma ideia ou descreva uma tarefa…" },
  { id: "image", label: "Imagem", icon: ImagePlus, placeholder: "Descreva a imagem, composição, iluminação, estilo e detalhes…" },
  { id: "video", label: "Vídeo", icon: Video, placeholder: "Descreva o vídeo, cenas, movimento de câmera e direção visual…" },
  { id: "website", label: "Site", icon: Globe2, placeholder: "Descreva o site, público, páginas, conteúdo e identidade visual…" },
  { id: "dashboard", label: "Dashboard", icon: ChartNoAxesCombined, placeholder: "Descreva os indicadores, filtros e dados que seu dashboard deve apresentar…" },
  { id: "automation", label: "Tarefas", icon: Workflow, placeholder: "Descreva o objetivo e os passos que deseja planejar com a Kiara…" },
] satisfies { id: ChatMode; label: string; icon: typeof MessageCircle; placeholder: string }[]
const capabilityLabels: Record<string, string> = { chat: "Conversa e análise", speech: "Voz da Kiara", transcribe: "Receber áudio", image: "Geração de imagens", video: "Geração de vídeos", website: "Criação de sites", dashboard: "Criação de dashboards", automation: "Automação da máquina" }
const prompts = [
  { mode: "chat" as const, icon: Sparkles, title: "Pense comigo", text: "Ajude a organizar as prioridades da minha operação e sugira próximos passos." },
  { mode: "website" as const, icon: Globe2, title: "Crie algo completo", text: "Crie um site institucional responsivo com apresentação, serviços, perguntas frequentes e contato." },
  { mode: "dashboard" as const, icon: ChartNoAxesCombined, title: "Transforme dados em visão", text: "Crie um dashboard comercial com indicadores e filtros. Identifique claramente todos os dados de demonstração." },
  { mode: "automation" as const, icon: Workflow, title: "Planeje uma tarefa", text: "Prepare um plano revisável para organizar arquivos e automatizar tarefas recorrentes no computador." },
]

function boundedHistory(messages: Message[]): ChatMessage[] {
  let remaining = 35_000
  return messages.slice(-24).reverse().flatMap((message) => {
    if (remaining <= 0) return []
    const content = message.content.slice(0, Math.min(10_000, remaining))
    remaining -= content.length
    return [{ role: message.role, content }]
  }).reverse()
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
  return <section className={styles.artifact} aria-label="Arquivo gerado">
    <div><span className={styles.artifactIcon}><Globe2 aria-hidden="true" /></span><div><strong>{artifact.name}</strong><p>HTML para revisar e baixar</p></div><Button type="button" variant="outline" onClick={() => setPreview(!preview)}>{preview ? "Fechar prévia" : "Ver prévia"}</Button><Button type="button" variant="outline" onClick={() => saveArtifact(artifact)} aria-label={`Baixar ${artifact.name}`}><Download aria-hidden="true" />Baixar</Button></div>
    {preview && <><p className={styles.previewNote}>Prévia isolada, sem acesso à sua conta ou a serviços externos.</p><iframe title={`Prévia de ${artifact.name}`} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={isolatedHtml(artifact.content)} /></>}
  </section>
}

export function ChatWorkspace() {
  const [transport, setTransport] = useState<ChatTransport>("cloud")
  const [status, setStatus] = useState<ChatStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [connectionError, setConnectionError] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [mode, setMode] = useState<ChatMode>("chat")
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [browserVoice, setBrowserVoice] = useState(false)
  const [audioUrl, setAudioUrl] = useState("")
  const abortRef = useRef<AbortController | null>(null)
  const statusAbortRef = useRef<AbortController | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const audioRef = useRef<HTMLAudioElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const draftRef = useRef<HTMLTextAreaElement>(null)
  const recordTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const activeMode = modes.find((item) => item.id === mode)!
  const capability = (id: string) => status?.capabilities.find((item) => item.id === id)
  const available = Boolean(status?.connected && capability(mode === "automation" ? "chat" : mode)?.available)
  const canTranscribe = Boolean(status?.connected && capability("transcribe")?.available)

  useEffect(() => {
    mountedRef.current = true
    setBrowserVoice("speechSynthesis" in window)
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
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content }
    const history = [...messages, userMessage]
    setMessages(history); setDraft(""); setBusy(true); setError(""); setNotice("")
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const action = mode === "chat" ? "chat" : mode === "website" || mode === "dashboard" ? "build" : mode === "automation" ? "plan" : mode
      const body = mode === "chat" ? { messages: boundedHistory(history) } : action === "build" ? { prompt: content, kind: mode } : { prompt: content }
      const reply = parseChatReply(await chatRequest(transport, action, body, controller.signal))
      if (!controller.signal.aborted) setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: reply.text, artifact: reply.artifact, plan: reply.plan }])
    } catch (reason) {
      if (controller.signal.aborted) setNotice("Geração interrompida. A solicitação pode já ter sido recebida pelo serviço.")
      else { setError(reason instanceof Error ? reason.message : "Não foi possível concluir a resposta."); setDraft(content) }
    } finally { setBusy(false); abortRef.current = null }
  }

  async function transcribe(file: File) {
    if (busy || !canTranscribe) return
    try {
      const mime = validateChatAudio(file)
      setBusy(true); setError(""); setNotice("Recebendo e transcrevendo seu áudio…")
      const controller = new AbortController()
      abortRef.current = controller
      const payload = await chatRequest(transport, "transcribe", { audio_base64: await blobBase64(file), mime, filename: file.name }, controller.signal) as { text?: unknown }
      if (controller.signal.aborted) return
      if (typeof payload?.text !== "string" || !payload.text.trim()) throw new Error("Não foi encontrada uma transcrição válida neste áudio.")
      setDraft((current) => `${current}${current ? "\n" : ""}${payload.text}`.slice(0, 10_000))
      setNotice("Áudio transcrito. Revise o texto e envie quando quiser.")
      draftRef.current?.focus()
    } catch (reason) { if (!(reason instanceof DOMException && reason.name === "AbortError")) setError(reason instanceof Error ? reason.message : "Não foi possível transcrever o áudio.") }
    finally { setBusy(false); abortRef.current = null; if (fileRef.current) fileRef.current.value = "" }
  }

  async function startRecording() {
    if (recording) { recorderRef.current?.stop(); return }
    if (busy || !canTranscribe) return
    setError("")
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Este navegador não oferece gravação. Use Anexar áudio para enviar um arquivo.")
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
      setRecording(true); setNotice("Gravando áudio. Clique em Parar gravação para transcrever. Limite de 60 segundos.")
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
        setNotice("Áudio da Kiara pronto. Use o player para ouvir.")
        setSpeaking(false)
      } else {
        if (!browserVoice) throw new Error("Voz indisponível neste navegador. Configure o serviço de voz local.")
        const utterance = new SpeechSynthesisUtterance(text.slice(0, 5000))
        utterance.lang = "pt-BR"
        const voice = window.speechSynthesis.getVoices().find((item) => item.lang.toLowerCase() === "pt-br")
        if (voice) utterance.voice = voice
        utterance.onend = () => setSpeaking(false)
        utterance.onerror = () => { setSpeaking(false); setError("A leitura de voz foi interrompida ou não está disponível.") }
        setSpeaking(true)
        window.speechSynthesis.speak(utterance)
      }
    } catch (reason) { setSpeaking(false); setError(reason instanceof Error ? reason.message : "Não foi possível gerar a voz.") }
  }

  return <section className={styles.workspace} aria-labelledby="kiara-chat-title">
    <header className={styles.header}>
      <div className={styles.identity}><span className={styles.logo}><AudioLines aria-hidden="true" /></span><div><p className={styles.eyebrow}>Seu espaço para pensar e criar</p><h1 id="kiara-chat-title">Kiara Chat<span>IA em ação, com contexto.</span></h1></div></div>
      <Button type="button" variant="outline" className={styles.newChat} onClick={() => { stopSpeech(); setMessages([]); setDraft(""); setError(""); setNotice(""); setMode("chat") }} disabled={busy || recording}><Plus aria-hidden="true" />Nova conversa</Button>
    </header>

    <div className={styles.connectionBar}>
      <span className={styles.connectionState} role="status"><i className={checking ? styles.pendingDot : status?.connected ? styles.onlineDot : styles.offlineDot} />{checking ? "Verificando IA…" : status?.connected ? `${transport === "local" ? "Serviço local" : "IA hospedada"} disponível` : "Aguardando conexão"}</span>
      <span className={styles.model}>{status?.model || "Modelo não confirmado"}</span>
      <label className={styles.transport}><span>Conexão</span><select value={transport} disabled={busy || recording || checking} onChange={(event) => void refreshConnection(event.target.value as ChatTransport)} aria-label="Conexão da inteligência"><option value="local">Neste computador</option><option value="cloud">Hospedada</option></select><ChevronDown aria-hidden="true" /></label>
      <Button type="button" variant="ghost" size="icon" aria-label="Verificar conexão da IA" onClick={() => void refreshConnection()} disabled={checking || busy || recording}>{checking ? <LoaderCircle className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}</Button>
    </div>
    {connectionError && <div className={styles.connectionError} role="status"><CircleHelp aria-hidden="true" /><div><strong>A conexão precisa de atenção</strong><p>{connectionError}</p><a href="#configuracoes">Como preparar a Kiara</a></div></div>}

    <div className={styles.workGrid}>
      <div id="conversa" className={styles.conversation}>
        <div className={styles.conversationTop}><span><MessageCircle aria-hidden="true" />Conversa atual</span><small>Histórico somente nesta página</small></div>
        <div className={styles.messageArea} role="log" aria-label="Mensagens da conversa" aria-live="polite" aria-relevant="additions">
          {!messages.length ? <div className={styles.welcome}><span className={styles.welcomeMark}><Sparkles aria-hidden="true" /></span><p className={styles.eyebrow}>Inteligência que acompanha seu trabalho</p><h2>O que vamos construir hoje?</h2><p>Converse, explore ideias, crie projetos e prepare tarefas. Os recursos disponíveis dependem dos serviços conectados à sua Kiara.</p><div className={styles.suggestions}>{prompts.map((prompt) => <button key={prompt.title} type="button" onClick={() => { setMode(prompt.mode); setDraft(prompt.text); draftRef.current?.focus() }}><prompt.icon aria-hidden="true" /><strong>{prompt.title}</strong><span>{prompt.text}</span></button>)}</div></div> : messages.map((message) => <article key={message.id} className={message.role === "assistant" ? styles.assistantMessage : styles.userMessage} aria-label={message.role === "assistant" ? "Resposta da Kiara" : "Sua mensagem"}><div className={styles.messageIdentity}><span>{message.role === "assistant" ? <Bot aria-hidden="true" /> : "V"}</span><strong>{message.role === "assistant" ? "Kiara" : "Você"}</strong></div><div className={styles.messageText}>{message.content}</div>{message.artifact && <Artifact artifact={message.artifact} />}{message.plan && <section className={styles.plan}><div><Workflow aria-hidden="true" /><strong>Plano para revisão</strong><span>Aguardando executor autorizado</span></div><ol>{message.plan.steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol><p>Este plano ainda não foi executado. Ações na máquina ou em sites dependem do executor e da autorização correspondente.</p></section>}{message.role === "assistant" && <button type="button" className={styles.speakButton} onClick={() => void speak(message.content)} disabled={speaking || busy}><Volume2 aria-hidden="true" />{capability("speech")?.available ? "Ouvir com a voz da Kiara" : "Ouvir com voz do navegador"}</button>}</article>)}
          {busy && <div className={styles.thinking} role="status"><LoaderCircle className="animate-spin motion-reduce:animate-none" /><span>{notice.startsWith("Recebendo") ? "Transcrevendo áudio…" : "A Kiara está trabalhando na sua solicitação…"}</span></div>}
        </div>
        <div className={styles.composerArea}>
          <div className={styles.modePicker} role="group" aria-label="Tipo de criação">{modes.map(({ id, label, icon: Icon }) => <button type="button" key={id} aria-pressed={mode === id} onClick={() => setMode(id)} disabled={busy || recording}><Icon aria-hidden="true" />{label}</button>)}</div>
          {!checking && !available && <p className={styles.modeUnavailable}>{mode === "automation" ? "Conecte um modelo de conversa para preparar um plano. A execução depende de um executor autorizado." : capability(mode)?.detail || `${activeMode.label}: recurso ainda não disponível nesta conexão.`}</p>}
          {mode === "automation" && available && <p className={styles.modeUnavailable}>A Kiara prepara o plano para revisão. Nenhuma ação na máquina será executada por esta conversa.</p>}
          <label className="sr-only" htmlFor="kiara-chat-message">Sua mensagem para a Kiara</label>
          <div className={styles.composer}><textarea ref={draftRef} id="kiara-chat-message" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={10_000} rows={3} placeholder={activeMode.placeholder} disabled={busy || recording} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } }} /><div className={styles.composerBottom}><div className={styles.inputActions}><input ref={fileRef} className="sr-only" type="file" accept="audio/webm,audio/ogg,audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/flac" onChange={(event) => { const file = event.target.files?.[0]; if (file) void transcribe(file) }} aria-label="Arquivo de áudio para transcrever" tabIndex={-1} /><button type="button" onClick={() => fileRef.current?.click()} disabled={busy || recording || !canTranscribe} aria-label="Anexar áudio" title={canTranscribe ? "Anexar áudio de até 5 MB" : "Conecte a transcrição de áudio para usar este recurso"}><Paperclip aria-hidden="true" /></button><button type="button" onClick={() => void startRecording()} disabled={busy || !canTranscribe} className={recording ? styles.recordingButton : undefined} aria-label={recording ? "Parar gravação" : "Gravar áudio"} aria-pressed={recording}>{recording ? <Square aria-hidden="true" /> : <Mic aria-hidden="true" />}</button><span>{recording ? "Gravando…" : "Áudio até 5 MB"}</span></div>{busy ? <Button type="button" variant="outline" onClick={() => abortRef.current?.abort()}><Square aria-hidden="true" />Interromper</Button> : <Button type="button" onClick={() => void send()} disabled={!draft.trim() || !available || checking || recording} className={styles.sendButton}><Send aria-hidden="true" />{mode === "automation" ? "Preparar plano" : "Enviar"}</Button>}</div></div>
          <div className={styles.composerNote}><span>Enter envia · Shift + Enter quebra a linha</span><span>{draft.length.toLocaleString("pt-BR")}/10.000</span></div>
          {error && <p role="alert" className={styles.error}><X aria-hidden="true" />{error}</p>}
          {notice && <p role="status" className={styles.notice}>{notice}</p>}
          {audioUrl && <div className={styles.audioPlayer}><AudioLines aria-hidden="true" /><audio ref={audioRef} controls src={audioUrl} onEnded={() => setSpeaking(false)}>Seu navegador não suporta reprodução de áudio.</audio></div>}
          {speaking && <button className={styles.speakButton} type="button" onClick={stopSpeech}><Square aria-hidden="true" />Parar voz</button>}
        </div>
      </div>

      <aside id="capacidades" className={styles.capabilityPanel} aria-labelledby="chat-capabilities-title"><div className={styles.capabilityHeading}><span><Sparkles aria-hidden="true" /></span><div><p className={styles.eyebrow}>Seu estúdio de possibilidades</p><h2 id="chat-capabilities-title">Recursos da Kiara</h2></div></div><p className={styles.capabilityIntro}>Cada recurso mostra o estado informado pelo serviço conectado.</p><ul>{Object.entries(capabilityLabels).map(([id, label]) => { const item = capability(id); return <li key={id}><span className={item?.available && status?.connected ? styles.capabilityReady : styles.capabilityPending}>{item?.available && status?.connected ? <Check aria-hidden="true" /> : <span aria-hidden="true">·</span>}</span><div><strong>{label}</strong><p>{checking ? "Verificando…" : item?.detail || "Serviço não conectado"}</p></div></li> })}</ul><div id="voz" className={styles.voiceInfo}><Volume2 aria-hidden="true" /><div><strong>{capability("speech")?.available ? "Voz da Kiara conectada" : browserVoice ? "Leitura com voz do navegador" : "Voz ainda não disponível"}</strong><p>O microfone só é acessado quando você inicia a gravação. Áudios transcritos ficam disponíveis para revisão antes do envio.</p></div></div><div className={styles.siteContext}><h3>A Kiara no seu site</h3><p>Abra o módulo para consultar os dados atuais da sua operação.</p><Link href="/app/leads">Leads e CRM<Globe2 aria-hidden="true" /></Link><Link href="/app/whatsapp">Central do WhatsApp<AudioLines aria-hidden="true" /></Link><Link href="/app/inbox">Caixa de entrada<MessageCircle aria-hidden="true" /></Link></div></aside>
    </div>

    <details id="configuracoes" className={styles.settings}><summary><span><Settings2 aria-hidden="true" /><strong>Conexão e configuração</strong></span><ChevronDown aria-hidden="true" /></summary><div><section><h2>IA neste computador</h2><p>Inicie a ponte local com <code>python scripts/run_kiara_chat.py</code>. Ela conecta os modelos e ferramentas instalados ao seu login Kiara. O navegador pode solicitar acesso à rede local.</p></section><section><h2>Recursos multimodais</h2><p>Voz, transcrição, imagem e vídeo precisam de seus modelos ou provedores configurados. A presença de um repositório não significa que ele está pronto para executar.</p></section><section><h2>Execução de tarefas</h2><p>Planos são apresentados para revisão. Operações no computador ou em sites dependem de um executor autorizado, dos limites de acesso e dos controles locais.</p></section><section><h2>Memória desta conversa</h2><p>O histórico desta tela fica em memória e é limpo ao recarregar ou iniciar uma nova conversa. Consulte a configuração do provedor conectado para conhecer sua política de dados.</p></section></div></details>
    <p className={styles.footerNote}><ShieldCheck aria-hidden="true" />Revise respostas, dados e arquivos antes de utilizá-los. A Kiara apresenta resultados e limites do serviço conectado.</p>
  </section>
}
