"use client"

import { useEffect, useRef, useState } from "react"
import { Mic, MicOff, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { VoiceOrb, type VoicePhase } from "./voice-orb"
import { pickFeminineVoice, speechChunks } from "@/lib/voice-text"
import { plainText } from "@/lib/chat-markdown"

/** Best female pt-BR voice the browser offers (never the default male one when a female exists). */
export function femininePortugueseVoice(): SpeechSynthesisVoice | undefined {
  return pickFeminineVoice(window.speechSynthesis.getVoices())
}

/** Minimal typing for the Web Speech API (Chrome exposes it as webkitSpeechRecognition). */
type RecognitionResult = { isFinal: boolean; 0: { transcript: string } }
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean
  onresult: ((event: { resultIndex: number; results: ArrayLike<RecognitionResult> }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void; stop(): void; abort(): void
}
type RecognitionConstructor = new () => Recognition

function recognitionConstructor(): RecognitionConstructor | null {
  const scope = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

/** Markdown and links read aloud sound robotic; keep only the spoken content. */
function speakable(text: string) {
  return plainText(text.replace(/```[\s\S]*?```/g, " (código omitido) ")).replace(/https?:\/\/\S+/g, " link ").replace(/[*_#>`|]/g, "").replace(/\s+/g, " ").trim().slice(0, 4000)
}

const phaseLabels: Record<VoicePhase, string> = {
  idle: "Microfone pausado", listening: "Ouvindo…", thinking: "Pensando…", speaking: "Falando…", error: "Algo deu errado",
}

const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA="
// One audio context and two players for the whole page: phones only let sound start from a tap, so they are
// unlocked in the tap that opens voice mode (primeVoiceAudio). The routed player feeds the orb with the real
// voice level but only plays while the context runs; the plain one always goes straight to the speakers.
let sharedContext: AudioContext | null = null
let routedAudio: HTMLAudioElement | null = null
let plainAudio: HTMLAudioElement | null = null
let outputAnalyser: AnalyserNode | null = null

function makeAudio() {
  const audio = new Audio()
  audio.preload = "auto"
  audio.setAttribute("playsinline", "")
  return audio
}

function sharedAudioContext(): AudioContext | null {
  try { return sharedContext ??= new AudioContext() } catch { return null }
}

/** Call inside the tap that opens voice mode (and on every orb tap): unlocks the players and the browser voice. */
export function primeVoiceAudio() {
  const context = sharedAudioContext()
  void context?.resume().catch(() => {})
  plainAudio ??= makeAudio()
  if (context && !routedAudio) {
    try {
      const audio = makeAudio()
      const analyser = context.createAnalyser()
      analyser.fftSize = 1024
      context.createMediaElementSource(audio).connect(analyser)
      analyser.connect(context.destination)
      routedAudio = audio
      outputAnalyser = analyser
    } catch { /* The plain player is enough. */ }
  }
  for (const audio of [plainAudio, routedAudio]) {
    if (!audio || !audio.paused) continue
    audio.src = SILENT_WAV
    void audio.play().catch(() => {})
  }
  try {
    if ("speechSynthesis" in window && !window.speechSynthesis.speaking) {
      const warm = new SpeechSynthesisUtterance(" ")
      warm.volume = 0
      window.speechSynthesis.speak(warm)
    }
  } catch { /* No browser voice. */ }
}

/** The routed player only while the context runs (a suspended context would play it silently). */
function voiceAudio(context: AudioContext | null): HTMLAudioElement {
  if (context?.state === "running" && routedAudio) return routedAudio
  return plainAudio ??= makeAudio()
}

export type VoiceBackends = {
  /** Sends the user's words to the chat and resolves with Kiara's reply; `onText` receives the reply while it is
   *  written, so Kiara starts speaking the first sentence before the rest arrives. */
  ask: (text: string, onText?: (soFar: string) => void) => Promise<string>
  /** Neural voice from the connected service, when available. */
  synthesize?: (text: string) => Promise<Blob>
  /** Server transcription, used when the browser cannot recognize speech. */
  transcribe?: (audio: Blob) => Promise<string>
}

/** Hands-free conversation: listen → think → speak → listen, with an orb that reacts to the live audio. */
export function VoiceConversation({ backends, onClose }: { backends: VoiceBackends; onClose: () => void }) {
  const [phase, setPhase] = useState<VoicePhase>("listening")
  const [error, setError] = useState("")
  const orbRef = useRef<HTMLDivElement>(null)
  const phaseRef = useRef<VoicePhase>("listening")
  const activeRef = useRef(true)
  const backendsRef = useRef(backends)
  const audioContextRef = useRef<AudioContext | null>(null)
  const micAnalyserRef = useRef<AnalyserNode | null>(null)
  const micStreamRef = useRef<MediaStream | null>(null)
  const recognitionRef = useRef<Recognition | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const turnRef = useRef(0)
  const syntheticRef = useRef(0)
  const stopSpeakingRef = useRef<(() => void) | null>(null)
  useEffect(() => { backendsRef.current = backends }, [backends])

  function go(next: VoicePhase) { phaseRef.current = next; setPhase(next) }

  useEffect(() => {
    activeRef.current = true
    const buffer = new Uint8Array(512)
    let frame = 0
    function rms(analyser: AnalyserNode | null) {
      if (!analyser) return 0
      analyser.getByteTimeDomainData(buffer)
      let sum = 0
      for (const value of buffer) { const centered = (value - 128) / 128; sum += centered * centered }
      return Math.min(1, Math.sqrt(sum / buffer.length) * 4)
    }
    // One animation loop feeds the orb with the level of whatever is active right now.
    function tick(time: number) {
      const current = phaseRef.current
      let level = 0
      if (current === "listening") level = micAnalyserRef.current ? rms(micAnalyserRef.current) : 0.08 + Math.sin(time / 450) * 0.05
      else if (current === "speaking") {
        if (outputAnalyser && routedAudio && !routedAudio.paused) level = rms(outputAnalyser)
        else if (plainAudio && !plainAudio.paused) level = 0.22 + Math.sin(time / 110) * 0.12
        else level = (syntheticRef.current = syntheticRef.current * 0.9)
      }
      else if (current === "thinking") level = 0.12 + Math.sin(time / 300) * 0.06
      orbRef.current?.style.setProperty("--level", level.toFixed(3))
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)

    // Per-run flag: a remount (e.g. React strict mode) must not inherit a stale microphone.
    let cancelled = false
    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
        if (cancelled) { stream.getTracks().forEach((track) => track.stop()); return }
        micStreamRef.current = stream
        const context = sharedAudioContext()
        audioContextRef.current = context
        if (context) {
          void context.resume().catch(() => {})
          const analyser = context.createAnalyser()
          analyser.fftSize = 1024
          const source = context.createMediaStreamSource(stream)
          source.connect(analyser)
          micSourceRef.current = source
          micAnalyserRef.current = analyser
        }
        listen()
      } catch {
        if (cancelled) return
        // The level meter is cosmetic; the browser recognizer opens the microphone on its own.
        if (recognitionConstructor()) listen()
        else fail("Permita o acesso ao microfone para conversar por voz.")
      }
    }
    void start()

    return () => {
      cancelled = true
      activeRef.current = false
      cancelAnimationFrame(frame)
      recognitionRef.current?.abort()
      if (recorderRef.current?.state === "recording") recorderRef.current.stop()
      stopSpeakingRef.current?.()
      micStreamRef.current?.getTracks().forEach((track) => track.stop())
      // The shared audio context stays open for the next conversation (it was unlocked by a tap).
      micSourceRef.current?.disconnect()
    }
    // The conversation loop is wired once for the lifetime of the overlay.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function fail(message: string) {
    setError(message); go("error")
  }

  function listen() {
    if (!activeRef.current) return
    setError(""); go("listening")
    const Constructor = recognitionConstructor()
    if (Constructor) return listenWithBrowser(Constructor)
    if (backendsRef.current.transcribe) return listenWithRecorder()
    fail("Este navegador não reconhece fala. Use o Chrome ou ative a transcrição na conexão local da Kiara.")
  }

  function listenWithBrowser(Constructor: RecognitionConstructor) {
    const recognition = new Constructor()
    recognition.lang = "pt-BR"
    recognition.interimResults = true
    // Continuous: a short breath in the middle of a sentence must not send half a question.
    recognition.continuous = true
    let finalText = ""
    let interimText = ""
    let silence: ReturnType<typeof setTimeout> | undefined
    recognition.onresult = (event) => {
      let finals = ""
      let interim = ""
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) finals += `${result[0].transcript} `
        else interim += result[0].transcript
      }
      finalText = finals
      interimText = interim
      // The turn ends after ~1 s without new words.
      clearTimeout(silence)
      silence = setTimeout(() => recognition.stop(), 1000)
    }
    let useRecorder = false
    recognition.onerror = (event) => {
      if (event.error === "no-speech" || event.error === "aborted") return
      if (event.error === "not-allowed" || event.error === "service-not-allowed") fail("O navegador bloqueou o reconhecimento de voz. Libere o microfone para este site.")
      else if (backendsRef.current.transcribe) useRecorder = true
      else fail("O reconhecimento de voz do navegador está indisponível agora. Verifique a internet ou ative a transcrição na conexão local.")
    }
    recognition.onend = () => {
      clearTimeout(silence)
      recognitionRef.current = null
      if (!activeRef.current || phaseRef.current !== "listening") return
      const said = `${finalText} ${interimText}`.replace(/\s+/g, " ").trim()
      if (said) void respond(said)
      else if (useRecorder) listenWithRecorder()
      // Silence: keep listening, with a small delay to avoid a hot restart loop.
      else setTimeout(() => { if (activeRef.current && phaseRef.current === "listening") listen() }, 250)
    }
    recognitionRef.current = recognition
    recognition.start()
  }

  function listenWithRecorder() {
    const stream = micStreamRef.current
    if (!stream) return
    const recorder = new MediaRecorder(stream)
    const chunks: Blob[] = []
    const buffer = new Uint8Array(512)
    let spoke = false
    let silentSince = 0
    const started = Date.now()
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
    recorder.onstop = async () => {
      recorderRef.current = null
      if (!activeRef.current || phaseRef.current !== "listening") return
      if (!spoke) { listen(); return }
      go("thinking")
      try {
        const text = (await backendsRef.current.transcribe!(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }))).trim()
        if (!activeRef.current) return
        if (text) await respond(text); else listen()
      } catch (reason) { fail(reason instanceof Error ? reason.message : "Não foi possível entender o áudio.") }
    }
    recorderRef.current = recorder
    recorder.start(250)
    // Simple voice activity detection: stop after ~1.2 s of silence following speech.
    const watch = () => {
      if (recorder.state !== "recording") return
      const analyser = micAnalyserRef.current
      let level = 0
      if (analyser) {
        analyser.getByteTimeDomainData(buffer)
        let sum = 0
        for (const value of buffer) { const centered = (value - 128) / 128; sum += centered * centered }
        level = Math.sqrt(sum / buffer.length)
      }
      const now = Date.now()
      if (level > 0.04) { spoke = true; silentSince = 0 } else if (spoke && !silentSince) silentSince = now
      if ((spoke && silentSince && now - silentSince > 1200) || now - started > 30_000) { recorder.stop(); return }
      setTimeout(watch, 100)
    }
    watch()
  }

  /** Kiara's reply is spoken sentence by sentence while it is still being written. */
  async function respond(text: string) {
    go("thinking")
    const turn = ++turnRef.current
    const speaker = createSpeaker(turn)
    let fed = 0
    const feed = (soFar: string, final = false) => {
      const rest = soFar.slice(fed)
      let cut = final ? rest.length : 0
      if (!final) {
        // Up to the last finished sentence, once there is enough to say.
        const last = [...rest.matchAll(/[.!?…]+["')\]]*\s/g)].at(-1)
        if (last?.index !== undefined && last.index + last[0].length >= 12) cut = last.index + last[0].length
      }
      if (cut <= 0) return
      speaker.say(rest.slice(0, cut))
      fed += cut
    }
    try {
      let streamed = ""
      const answer = await backendsRef.current.ask(text, (soFar) => { streamed = soFar; if (turnRef.current === turn) feed(soFar) })
      if (!activeRef.current || turnRef.current !== turn) return
      // What was not spoken yet; nothing more when the final text no longer matches what was already said.
      if (!streamed || answer.startsWith(streamed.slice(0, fed))) feed(answer, true)
      await speaker.done()
      if (activeRef.current && turnRef.current === turn && (phaseRef.current === "speaking" || phaseRef.current === "thinking")) listen()
    } catch (reason) {
      if (activeRef.current && turnRef.current === turn) fail(reason instanceof Error ? reason.message : "A Kiara não conseguiu responder.")
    }
  }

  /** Each sentence's audio is prepared as soon as it arrives; playback keeps the order. */
  function createSpeaker(turn: number) {
    let chain = Promise.resolve()
    const current = () => activeRef.current && turnRef.current === turn
    return {
      say(raw: string) {
        const spoken = speakable(raw)
        if (!spoken) return
        const synthesize = backendsRef.current.synthesize
        const pieces = speechChunks(spoken).map((part) => ({ part, audio: synthesize ? synthesize(part).catch(() => null) : Promise.resolve(null) }))
        chain = chain.then(async () => {
          for (const { part, audio } of pieces) {
            if (!current()) return
            if (phaseRef.current === "thinking") go("speaking")
            if (phaseRef.current !== "speaking") return
            const blob = await audio
            if (!current() || phaseRef.current !== "speaking") return
            if (blob && await playAudio(blob)) continue
            // No neural voice, or the browser refused to play it: the browser voice says this part.
            await speakWithBrowser(part)
          }
        })
      },
      done: () => chain,
    }
  }

  /** Plays one prepared sentence; false when the browser refused to play it. */
  async function playAudio(blob: Blob): Promise<boolean> {
    const context = audioContextRef.current ?? sharedContext
    if (context && context.state !== "running") await context.resume().catch(() => {})
    const audio = voiceAudio(context)
    const url = URL.createObjectURL(blob)
    try {
      return await new Promise<boolean>((resolve) => {
        const finish = (played: boolean) => { stopSpeakingRef.current = null; resolve(played) }
        audio.onended = () => finish(true)
        audio.onerror = () => finish(false)
        stopSpeakingRef.current = () => { audio.pause(); finish(true) }
        audio.src = url
        audio.play().catch(() => finish(false))
      })
    } finally {
      URL.revokeObjectURL(url)
    }
  }

  /** Sentence by sentence: Chrome silently cuts long utterances, which left Kiara's sentences unfinished. */
  async function speakWithBrowser(text: string) {
    if (!("speechSynthesis" in window) || !text) return
    window.speechSynthesis.cancel()
    for (const part of speechChunks(text)) {
      if (!activeRef.current || phaseRef.current !== "speaking") return
      await speakUtterance(part)
    }
  }

  function speakUtterance(text: string) {
    return new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = "pt-BR"
      const voice = femininePortugueseVoice()
      if (voice) utterance.voice = voice
      // The browser voice exposes no audio stream; each spoken word gives the orb a pulse.
      utterance.onboundary = () => { syntheticRef.current = 0.55 + Math.random() * 0.35 }
      const finish = () => { stopSpeakingRef.current = null; resolve() }
      utterance.onend = finish
      utterance.onerror = finish
      stopSpeakingRef.current = () => { window.speechSynthesis.cancel(); finish() }
      window.speechSynthesis.speak(utterance)
    })
  }

  /** Tapping the orb interrupts Kiara and gives the turn back to the user, or pauses/resumes listening. */
  function pressOrb() {
    primeVoiceAudio()
    if (phaseRef.current === "speaking") {
      turnRef.current += 1
      stopSpeakingRef.current?.()
      if ("speechSynthesis" in window) window.speechSynthesis.cancel()
      listen()
      return
    }
    if (phaseRef.current === "listening") { pause(); return }
    if (phaseRef.current === "idle" || phaseRef.current === "error") listen()
  }

  function pause() {
    recognitionRef.current?.abort()
    if (recorderRef.current?.state === "recording") { go("idle"); recorderRef.current.stop() }
    go("idle")
  }

  const muted = phase === "idle"
  return <div className="fixed inset-0 z-[120] flex flex-col bg-background/95 backdrop-blur-xl" role="dialog" aria-modal="true" aria-label="Conversa por voz com a Kiara">
    <div className="flex justify-end p-4"><Button type="button" variant="ghost" size="icon" aria-label="Encerrar conversa por voz" onClick={onClose}><X /></Button></div>
    <div className="flex flex-1 flex-col items-center justify-center gap-8 px-6 text-center">
      <VoiceOrb ref={orbRef} phase={phase} label={phase === "speaking" ? "Interromper a Kiara" : phase === "listening" ? "Pausar o microfone" : "Voltar a ouvir"} onPress={pressOrb} />
      <div className="min-h-16 max-w-xl space-y-3" aria-live="polite">
        <p className="text-sm font-medium text-muted-foreground">{phaseLabels[phase]}</p>
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      </div>
    </div>
    <div className="flex items-center justify-center gap-4 pb-[max(2rem,env(safe-area-inset-bottom))]">
      <Button type="button" variant="outline" size="icon" className="size-14 rounded-full" aria-label={muted ? "Ativar microfone" : "Pausar microfone"} aria-pressed={muted} onClick={() => (muted ? listen() : pause())} disabled={phase === "thinking"}>{muted ? <MicOff /> : <Mic />}</Button>
      <Button type="button" size="icon" className="size-14 rounded-full bg-destructive text-white hover:bg-destructive/90" aria-label="Encerrar" onClick={onClose}><X /></Button>
    </div>
    <p className="pb-4 text-center text-xs text-muted-foreground">Toque no orbe para interromper a Kiara ou pausar o microfone.</p>
  </div>
}
