import { connectionLabels, nodeKind, type FlowNode, type Workflow } from "./catalog"
import { leadDisplayName, parsePipeline, pipelineStages, requestPipeline, type PipelineEntry } from "@/lib/api/pipeline"

export type StepStatus = "running" | "done" | "blocked" | "error"
export type Step = { nodeId: string; status: StepStatus; output?: string; message?: string }
export type RunContext = {
  /** Sends a prompt to Kiara's AI and resolves with the reply text. */
  ask: (prompt: string) => Promise<string>
  onStep: (step: Step) => void
  signal: AbortSignal
}

const MAX_STEPS = 60
const MAX_TEXT = 8000

class Blocked extends Error {}

function fill(template: string | number | undefined, input: string) {
  return String(template ?? "").replaceAll("{{entrada}}", input).replaceAll("{{lead}}", input)
}

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("Execução interrompida.", "AbortError")) }, { once: true })
  })
}

function describeLead(entry: PipelineEntry) {
  const stage = pipelineStages.find((item) => item.id === entry.stage)?.label ?? entry.stage
  return [leadDisplayName(entry.consumer), entry.consumer.phone, entry.consumer.address, `etapa: ${stage}`, entry.next_action ? `próxima ação: ${entry.next_action}` : ""].filter(Boolean).join(" · ")
}

async function leads() {
  return parsePipeline(await requestPipeline("/api/pipeline")).sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

/** Runs JavaScript in a throwaway worker: no DOM, no page state, 3 s limit. */
function runCode(code: string, input: string, signal: AbortSignal) {
  const source = `onmessage = async (event) => { try { const entrada = event.data; const result = await (async () => { ${code}\n })(); postMessage({ ok: true, value: typeof result === "string" ? result : JSON.stringify(result) }) } catch (error) { postMessage({ ok: false, value: String(error && error.message || error) }) } }`
  const url = URL.createObjectURL(new Blob([source], { type: "text/javascript" }))
  const worker = new Worker(url)
  URL.revokeObjectURL(url)
  return new Promise<string>((resolve, reject) => {
    const stop = (error: Error) => { worker.terminate(); reject(error) }
    const timer = setTimeout(() => stop(new Error("O código passou de 3 segundos e foi interrompido.")), 3000)
    signal.addEventListener("abort", () => { clearTimeout(timer); stop(new DOMException("Execução interrompida.", "AbortError")) }, { once: true })
    worker.onmessage = (event) => { clearTimeout(timer); worker.terminate(); if (event.data.ok) resolve(String(event.data.value ?? "")); else reject(new Error(event.data.value)) }
    worker.onerror = (event) => { clearTimeout(timer); stop(new Error(event.message || "Erro no código.")) }
    worker.postMessage(input)
  })
}

async function execute(node: FlowNode, input: string, context: RunContext): Promise<{ output: string; port?: "yes" | "no" }> {
  const kind = nodeKind(node.type)
  if (!kind) throw new Error("Bloco desconhecido.")
  if (kind.run !== "browser") throw new Blocked(`Precisa de: ${connectionLabels[kind.run]}.`)
  const config = node.config
  switch (node.type) {
    case "trigger.manual":
    case "trigger.schedule":
      return { output: input }
    case "trigger.lead": {
      const latest = (await leads())[0]
      if (!latest) throw new Error("Ainda não há leads no CRM.")
      return { output: describeLead(latest) }
    }
    case "ai.generate":
      return { output: (await context.ask(fill(config.prompt, input))).slice(0, MAX_TEXT) }
    case "ai.classify": {
      const answer = await context.ask(`${fill(config.question, input)}\n\nResponda apenas com SIM ou NÃO.`)
      return { output: /\bsim\b/i.test(answer) && !/\bn[ãa]o\b/i.test(answer) ? "SIM" : "NÃO" }
    }
    case "logic.condition": {
      const needle = String(config.contains ?? "").trim().toLowerCase()
      return { output: input, port: needle && input.toLowerCase().includes(needle) ? "yes" : "no" }
    }
    case "logic.delay":
      await wait(Math.min(60, Math.max(1, Number(config.seconds) || 1)) * 1000, context.signal)
      return { output: input }
    case "logic.notify":
      if (typeof Notification !== "undefined" && Notification.permission === "granted") new Notification(String(config.title || "Kiara Automation"), { body: input.slice(0, 180) })
      return { output: input }
    case "crm.read": {
      const stage = String(config.stage || "active")
      const selected = (await leads()).filter((entry) => stage === "active" ? !["won", "lost"].includes(entry.stage) : entry.stage === stage)
      const limit = Math.min(50, Math.max(1, Number(config.limit) || 10))
      return { output: selected.length ? selected.slice(0, limit).map(describeLead).join("\n") : "Nenhum lead nessa etapa." }
    }
    case "web.http": {
      const url = fill(config.url, input).trim()
      if (!/^https:\/\//i.test(url)) throw new Error("Informe um endereço https.")
      let response: Response
      try { response = await fetch(url, { signal: context.signal, credentials: "omit", referrerPolicy: "no-referrer" }) }
      catch { throw new Error("O site não permitiu a consulta pelo navegador (CORS) ou está fora do ar. Use o executor para este site.") }
      if (!response.ok) throw new Error(`O site respondeu com erro ${response.status}.`)
      return { output: (await response.text()).slice(0, MAX_TEXT) }
    }
    case "code.js":
      return { output: (await runCode(String(config.code ?? ""), input, context.signal)).slice(0, MAX_TEXT) }
    default:
      throw new Blocked("Este bloco ainda não executa nesta página.")
  }
}

/**
 * Walks the flow from its triggers. A blocked step (missing connection) stops only its own branch;
 * nothing is simulated as a success.
 */
export async function runWorkflow(workflow: Workflow, context: RunContext) {
  const triggers = workflow.nodes.filter((node) => nodeKind(node.type)?.trigger)
  if (!triggers.length) throw new Error("Adicione um gatilho para iniciar o fluxo.")
  const queue = triggers.map((node) => ({ node, input: "" }))
  let steps = 0
  while (queue.length) {
    if (context.signal.aborted) throw new DOMException("Execução interrompida.", "AbortError")
    if (++steps > MAX_STEPS) throw new Error(`O fluxo passou de ${MAX_STEPS} passos e foi interrompido (verifique se há um ciclo).`)
    const { node, input } = queue.shift()!
    context.onStep({ nodeId: node.id, status: "running" })
    let result: { output: string; port?: "yes" | "no" }
    try {
      result = await execute(node, input, context)
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error
      context.onStep({ nodeId: node.id, status: error instanceof Blocked ? "blocked" : "error", message: error instanceof Error ? error.message : "Falha no bloco." })
      continue
    }
    context.onStep({ nodeId: node.id, status: "done", output: result.output })
    for (const edge of workflow.edges.filter((item) => item.from === node.id && (!result.port || (item.port ?? "yes") === result.port))) {
      const next = workflow.nodes.find((item) => item.id === edge.to)
      if (next) queue.push({ node: next, input: result.output })
    }
  }
}
