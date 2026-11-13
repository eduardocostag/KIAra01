"use client"

import { useEffect, useRef, useState } from "react"
import { Mic, MicOff, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { VoiceOrb, type VoicePhase } from "./voice-orb"
import { pickFeminineVoice, speechChunks } from "@/lib/voice-text"

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
  start(): void; abort(): void
}
type RecognitionConstructor = new () => Recognition

function recognitionConstructor(): RecognitionConstructor | null {
  const scope = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

/** Markdown and links read aloud sound robotic; keep only the spoken content. */
function speakable(text: string) {
  return text.replace(/```[\s\S]*?```/g, " (código omitido) ").replace(/https?:\/\/\S+/g, " link ").replace(/[*_#>`|]/g, "").replace(/\s+/g, " ").trim().slice(0, 4000)
}

const phaseLabels: Record<VoicePhase, string> = {
  idle: "Microfone pausado", listening: "Ouvindo…", thinking: "Pensando…", speaking: "Falando…", error: "Algo deu errado",
}

export type VoiceBackends = {
  /** Sends the user's words to the chat and resolves with Kiara's reply. */
  ask: (text: string) => Promise<string>
  /** Neural voice from the connected service, when available. */
  synthesize?: (text: string) => Promise<Blob>
  /** Server transcription, used when the browser cannot recognize speech. */
  transcribe?: (audio: Blob) => Promise<string>
}

/** Hands-free conversation: listen → think → speak → listen, with an orb that reacts to the live audio. */
export function VoiceConversation({ backends, onClose }: { backends: VoiceBackends; onClose: () => void }) {
  const [phase, setPhase] = useState<VoicePhase>("listening")
  const [heard, setHeard] = useState("")
  const [reply, setReply] = useState("")
  const [error, setError] = useState("")
  const orbRef = useRef<HTMLDivElement>(null)
  const phaseRef = useRef<VoicePhase>("listening")
  const activeRef = useRef(true)
  const backendsRef = useRef(backends)
  const audioContextRef = useRef<AudioContext | null>(null)
  const micAnalyserRef = useRef<AnalyserNode | null>(null)
  const outAnalyserRef = useRef<AnalyserNode | null>(null)
  const micStreamRef = useRef<MediaStream | null>(null)
  const recognitionRef = useRef<Recognition | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
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
      else if (current === "speaking") level = outAnalyserRef.current && audioRef.current && !audioRef.current.paused ? rms(outAnalyserRef.current) : (syntheticRef.current = syntheticRef.current * 0.9)
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
        const context = new AudioContext()
        audioContextRef.current = context
        const analyser = context.createAnalyser()
        analyser.fftSize = 1024
        context.createMediaStreamSource(stream).connect(analyser)
        micAnalyserRef.current = analyser
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
      void audioContextRef.current?.close()
    }
    // The conversation loop is wired once for the lifetime of the overlay.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function fail(message: string) {
    setError(message); go("error")
  }

  function listen() {
    if (!activeRef.current) return
    setError(""); setHeard(""); go("listening")
    const Constructor = recognitionConstructor()
    if (Constructor) return listenWithBrowser(Constructor)
    if (backendsRef.current.transcribe) return listenWithRecorder()
    fail("Este navegador não reconhece fala. Use o Chrome ou ative a transcrição na conexão local da Kiara.")
  }

  function listenWithBrowser(Constructor: RecognitionConstructor) {
    const recognition = new Constructor()
    recognition.lang = "pt-BR"
    recognition.interimResults = true
    recognition.continuous = false
    let finalText = ""
    recognition.onresult = (event) => {
      let interim = ""
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) finalText += result[0].transcript
        else interim += result[0].transcript
      }
      setHeard((finalText + interim).trim())
    }
    let useRecorder = false
    recognition.onerror = (event) => {
      if (event.error === "no-speech" || event.error === "aborted") return
      if (event.error === "not-allowed" || event.error === "service-not-allowed") fail("O navegador bloqueou o reconhecimento de voz. Libere o microfone para este site.")
      else if (backendsRef.current.transcribe) useRecorder = true
      else fail("O reconhecimento de voz do navegador está indisponível agora. Verifique a internet ou ative a transcrição na conexão local.")
    }
    recognition.onend = () => {
      recognitionRef.current = null
      if (!activeRef.current || phaseRef.current !== "listening") return
      if (finalText.trim()) void respond(finalText.trim())
      else if (useRecorder) listenWithRecorder()
      // Silence or a short pause: keep listening, with a small delay to avoid a hot restart loop.
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
        if (text) { setHeard(text); await respond(text) } else listen()
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

  async function respond(text: string) {
    go("thinking"); setReply("")
    try {
      const answer = await backendsRef.current.ask(text)
      if (!activeRef.current) return
      setReply(answer)
      await speak(answer)
      if (activeRef.current && phaseRef.current === "speaking") listen()
    } catch (reason) {
      if (activeRef.current) fail(reason instanceof Error ? reason.message : "A Kiara não conseguiu responder.")
    }
  }

  async function speak(text: string) {
    go("speaking")
    const spoken = speakable(text)
    const synthesize = backendsRef.current.synthesize
    if (synthesize) {
      // Sentence by sentence: Kiara starts talking after the first one is ready while the next is prepared.
      const parts = speechChunks(spoken)
      let index = 0
      try {
        let next = synthesize(parts[0])
        for (; index < parts.length; index += 1) {
          const blob = await next
          if (index + 1 < parts.length) next = synthesize(parts[index + 1])
          if (!activeRef.current || phaseRef.current !== "speaking") return
          await playAudio(blob)
        }
        return
      } catch {
        // Fall back to the browser voice for whatever was not spoken yet.
        if (!activeRef.current || phaseRef.current !== "speaking") return
        await speakWithBrowser(parts.slice(index).join(" "))
        return
      }
    }
    await speakWithBrowser(spoken)
  }

  function playAudio(blob: Blob) {
    return new Promise<void>((resolve) => {
      const context = audioContextRef.current
      let audio = audioRef.current
      if (!audio) {
        audio = new Audio()
        audioRef.current = audio
        if (context) {
          // Route the voice through an analyser so the orb follows the real output level.
          const analyser = context.createAnalyser()
          analyser.fftSize = 1024
          const source = context.createMediaElementSource(audio)
          source.connect(analyser)
          analyser.connect(context.destination)
          outAnalyserRef.current = analyser
        }
      }
      const url = URL.createObjectURL(blob)
      const finish = () => { URL.revokeObjectURL(url); stopSpeakingRef.current = null; resolve() }
      audio.onended = finish
      audio.onerror = finish
      stopSpeakingRef.current = () => { audio!.pause(); finish() }
      audio.src = url
      void context?.resume()
      audio.play().catch(finish)
    })
  }

  function speakWithBrowser(text: string) {
    return new Promise<void>((resolve) => {
      if (!("speechSynthesis" in window) || !text) { resolve(); return }
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
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(utterance)
    })
  }

  /** Tapping the orb interrupts Kiara and gives the turn back to the user, or pauses/resumes listening. */
  function pressOrb() {
    if (phaseRef.current === "speaking") { stopSpeakingRef.current?.(); listen(); return }
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
      <div className="min-h-28 max-w-xl space-y-3" aria-live="polite">
        <p className="text-sm font-medium text-muted-foreground">{phaseLabels[phase]}</p>
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p>
          : phase === "listening" || phase === "thinking" ? <p className="text-lg leading-7">{heard || (phase === "listening" ? "Pode falar." : "")}</p>
            : reply ? <p className="line-clamp-4 text-lg leading-7 text-foreground/90">{reply}</p> : null}
      </div>
    </div>
    <div className="flex items-center justify-center gap-4 pb-[max(2rem,env(safe-area-inset-bottom))]">
      <Button type="button" variant="outline" size="icon" className="size-14 rounded-full" aria-label={muted ? "Ativar microfone" : "Pausar microfone"} aria-pressed={muted} onClick={() => (muted ? listen() : pause())} disabled={phase === "thinking"}>{muted ? <MicOff /> : <Mic />}</Button>
      <Button type="button" size="icon" className="size-14 rounded-full bg-destructive text-white hover:bg-destructive/90" aria-label="Encerrar" onClick={onClose}><X /></Button>
    </div>
    <p className="pb-4 text-center text-xs text-muted-foreground">Toque no orbe para interromper a Kiara ou pausar o microfone.</p>
  </div>
}
