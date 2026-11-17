"use client"

import { useEffect, useState } from "react"
import { Brain, Loader2, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { growth } from "@/lib/api/growth"

type Memory = { id: string; fact: string; source: "chat" | "manual" | "learned"; updated_at: string }
type MemoryList = { items: Memory[]; limit: number }

/** What Kiara remembers from earlier chats: the owner can read, add and delete each fact. */
export function MemoryPanel() {
  const [data, setData] = useState<MemoryList | null>(null)
  const [fact, setFact] = useState("")
  const [busy, setBusy] = useState("")
  const [message, setMessage] = useState("")

  useEffect(() => { growth<MemoryList>("memory").then(setData).catch(() => setData({ items: [], limit: 60 })) }, [])

  async function run(key: string, action: () => Promise<unknown>, done: string) {
    setBusy(key); setMessage("")
    try { await action(); setData(await growth<MemoryList>("memory")); setMessage(done) }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Não foi possível agora.") }
    finally { setBusy("") }
  }

  return <section aria-labelledby="memory-title" className="kiara-soft-panel space-y-4 rounded-2xl border p-5 sm:p-6">
    <div>
      <h2 id="memory-title" className="flex items-center gap-2 text-lg font-semibold"><Brain className="size-5 text-primary" aria-hidden="true" />O que a Kiara lembra</h2>
      <p className="text-sm text-muted-foreground">Quando você conta algo no chat (ou pede “lembre disso”), a Kiara guarda aqui e usa nas próximas conversas. Ela também aprende sozinha com as suas buscas de leads: o que vira cliente e o que não dá resultado. Apague o que não quiser que ela lembre.</p>
    </div>
    <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); const text = fact.trim(); if (text.length >= 3) void run("add", () => growth("memory", { method: "POST", body: JSON.stringify({ fact: text }) }).then(() => setFact("")), "Guardado.") }}>
      <label htmlFor="memory-fact" className="sr-only">Algo para a Kiara lembrar</label>
      <input id="memory-fact" value={fact} onChange={(event) => setFact(event.target.value)} maxLength={300} placeholder="Ex.: Prefiro respostas curtas e diretas" className="h-10 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary/50" />
      <Button type="submit" disabled={busy === "add" || fact.trim().length < 3}>{busy === "add" ? <Loader2 className="animate-spin" /> : <Plus />}<span className="hidden sm:inline">Lembrar</span></Button>
    </form>
    {message ? <p role="status" className="text-xs text-muted-foreground">{message}</p> : null}
    {!data ? <div className="fx-skeleton h-16 rounded-xl" aria-label="Carregando" />
      : data.items.length ? <ul className="divide-y rounded-xl border">{data.items.map((item) => <li key={item.id} className="flex items-start gap-3 p-3">
        <span className="min-w-0 flex-1 text-sm">{item.fact}<span className="mt-0.5 block text-[11px] text-muted-foreground">{item.source === "manual" ? "Você escreveu" : item.source === "learned" ? "Aprendido com as suas buscas" : "Aprendido no chat"} · {new Date(item.updated_at).toLocaleDateString("pt-BR")}</span></span>
        <button type="button" aria-label={`Esquecer: ${item.fact}`} disabled={busy === item.id} className="shrink-0 text-muted-foreground hover:text-destructive disabled:opacity-50" onClick={() => void run(item.id, () => growth(`memory/${item.id}`, { method: "DELETE" }), "Esquecido.")}><Trash2 className="size-4" /></button>
      </li>)}</ul>
        : <p className="text-sm text-muted-foreground">Ainda nada. Converse com a Kiara: ela aprende seu nome, como funciona o seu negócio e como você gosta das respostas.</p>}
    {data?.items.length ? <p className="text-[11px] text-muted-foreground">{data.items.length} de {data.limit} lembranças. Senhas, códigos e números de cartão nunca são guardados.</p> : null}
  </section>
}
