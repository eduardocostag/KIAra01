"use client"

import { AdminOnly } from "@/components/app-shell/admin-access"

import Link from "next/link"
import { useEffect, useRef, useState, type CSSProperties } from "react"
import { Check, ChevronDown, CircleAlert, Copy, LayoutTemplate, LoaderCircle, Maximize2, Play, Plug, Plus, Search, Square, Trash2, Workflow as WorkflowIcon, X, ZoomIn, ZoomOut } from "lucide-react"
import { ImmersiveShell } from "@/components/app-shell/immersive-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { adsBilling, categories, connectionLabels, emptyWorkflow, newId, nodeKind, nodeKinds, templates, type CategoryId, type FlowNode, type NodeKind, type Workflow } from "@/lib/automation/catalog"
import { runWorkflow, type Step, type StepStatus } from "@/lib/automation/runner"
import { chatRequest, parseChatReply, type ChatTransport } from "@/lib/chat-client"
import { cn } from "@/lib/utils"
import { FlowCanvas, NODE_DRAG_TYPE, NODE_HEIGHT, NODE_WIDTH, NodeIcon, type View } from "./flow-canvas"

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })
const statusLabels: Record<StepStatus, string> = { running: "Executando", done: "Concluído", blocked: "Precisa conectar", error: "Erro" }

function readFlows(key: string): Workflow[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "[]")
    return Array.isArray(value) ? value.filter((item): item is Workflow => typeof item?.id === "string" && Array.isArray(item?.nodes) && Array.isArray(item?.edges)) : []
  } catch { return [] }
}

function AdsCost({ kind, node }: { kind: NodeKind; node: FlowNode }) {
  const billing = adsBilling[kind.ads!]
  const daily = Math.max(0, Number(node.config.daily) || 0)
  const days = Math.max(0, Number(node.config.days) || 0)
  return <section className="space-y-3 rounded-xl border border-amber-400/30 bg-amber-400/5 p-4" aria-label="Custos do anúncio">
    <p className="text-sm font-semibold">Quanto vai custar</p>
    <div className="grid grid-cols-2 gap-2 text-sm">
      <div className="rounded-lg bg-background/60 p-2"><p className="text-xs text-muted-foreground">Por dia</p><p className="font-semibold tabular-nums">{brl.format(daily)}</p></div>
      <div className="rounded-lg bg-background/60 p-2"><p className="text-xs text-muted-foreground">Total em {days} dia(s)</p><p className="font-semibold tabular-nums">{brl.format(daily * days)}</p></div>
    </div>
    {billing.monthlyCap ? <p className="text-xs text-muted-foreground">Teto do Google: até {brl.format(daily * 2)} em um dia e no máximo {brl.format(daily * billing.monthlyCap)} por mês.</p> : null}
    <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">{billing.how.map((line) => <li key={line}>{line}</li>)}<li>{billing.minimum}</li></ul>
    <p className="text-xs text-muted-foreground">O valor é o que você autoriza gastar na plataforma, não uma previsão de resultado. A IA da Kiara que escreve os anúncios usa o provedor configurado no seu roteador (OmniRoute).</p>
  </section>
}

export function AutomationWorkspace({ userId = "preview" }: { userId?: string }) {
  const storageKey = `kiara-automation:${userId}`
  const [flows, setFlows] = useState<Workflow[]>([])
  const [activeId, setActiveId] = useState("")
  const [view, setView] = useState<View>({ x: 40, y: 40, zoom: 1 })
  const [selectedId, setSelectedId] = useState("")
  const [paletteOpen, setPaletteOpen] = useState(true)
  const [search, setSearch] = useState("")
  const [statuses, setStatuses] = useState<Record<string, StepStatus>>({})
  const [steps, setSteps] = useState<Step[]>([])
  const [activeEdges, setActiveEdges] = useState<Set<string>>(new Set())
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState("")
  const [logOpen, setLogOpen] = useState(false)
  const areaRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const transportRef = useRef<ChatTransport | null>(null)
  const flow = flows.find((item) => item.id === activeId)
  const selected = flow?.nodes.find((node) => node.id === selectedId)
  const selectedKind = selected ? nodeKind(selected.type) : undefined

  // Flows are kept in this browser, per signed-in user.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { const saved = readFlows(storageKey); setFlows(saved); setActiveId(saved[0]?.id ?? "") }, [storageKey])

  function persist(next: Workflow[]) {
    setFlows(next)
    try { localStorage.setItem(storageKey, JSON.stringify(next.slice(0, 50))) } catch { /* Storage blocked: keep in memory. */ }
  }
  function update(next: Workflow) { persist(flows.map((item) => item.id === next.id ? { ...next, updatedAt: Date.now() } : item)) }
  function open(next: Workflow) {
    persist([next, ...flows.filter((item) => item.id !== next.id)])
    setActiveId(next.id); setSelectedId(""); setStatuses({}); setSteps([]); setRunError("")
    requestAnimationFrame(() => fit(next))
  }
  function remove(id: string) {
    const next = flows.filter((item) => item.id !== id)
    persist(next)
    if (id === activeId) setActiveId(next[0]?.id ?? "")
  }

  /** Part of the canvas not covered by the floating palette and inspector. */
  function visibleArea(inspectorOpen: boolean) {
    const area = areaRef.current?.getBoundingClientRect()
    if (!area) return null
    const wide = area.width > 900
    const left = paletteOpen && wide ? 290 : 24, right = area.width - (inspectorOpen && wide ? 370 : 24)
    return { left, right, top: 24, bottom: area.height - 90 }
  }

  function fit(target = flow) {
    const box = visibleArea(Boolean(selectedId))
    if (!target?.nodes.length || !box) return
    const minX = Math.min(...target.nodes.map((node) => node.x)), maxX = Math.max(...target.nodes.map((node) => node.x + NODE_WIDTH))
    const minY = Math.min(...target.nodes.map((node) => node.y)), maxY = Math.max(...target.nodes.map((node) => node.y + NODE_HEIGHT))
    const width = box.right - box.left, height = box.bottom - box.top
    const zoom = Math.min(1.1, Math.max(0.35, Math.min((width - 40) / (maxX - minX || 1), (height - 40) / (maxY - minY || 1))))
    setView({ zoom, x: box.left + (width - (maxX - minX) * zoom) / 2 - minX * zoom, y: box.top + (height - (maxY - minY) * zoom) / 2 - minY * zoom })
  }

  /** Pans just enough to bring a node out from under the floating panels. */
  function reveal(node: FlowNode) {
    const box = visibleArea(true)
    if (!box) return
    const left = node.x * view.zoom + view.x, top = node.y * view.zoom + view.y
    const right = left + NODE_WIDTH * view.zoom, bottom = top + NODE_HEIGHT * view.zoom
    if (left >= box.left && right <= box.right && top >= box.top && bottom <= box.bottom) return
    setView({ ...view, x: (box.left + box.right) / 2 - (node.x + NODE_WIDTH / 2) * view.zoom, y: (box.top + box.bottom) / 2 - (node.y + NODE_HEIGHT / 2) * view.zoom })
  }

  function addNode(type: string, at?: { x: number; y: number }) {
    if (!flow) return
    const kind = nodeKind(type)
    const area = areaRef.current?.getBoundingClientRect()
    const center = at ?? { x: ((area?.width ?? 800) / 2 - view.x) / view.zoom - NODE_WIDTH / 2, y: ((area?.height ?? 500) / 2 - view.y) / view.zoom - NODE_HEIGHT / 2 }
    const node: FlowNode = { id: newId("n"), type, x: Math.round(center.x), y: Math.round(center.y), config: { ...kind?.defaults } }
    // Clicking a block after selecting another one wires them together automatically.
    const auto = !at && selected && !kind?.trigger && !nodeKind(selected.type)?.branches ? [{ id: newId("e"), from: selected.id, to: node.id }] : []
    if (!at && selected) { node.x = selected.x + NODE_WIDTH + 70; node.y = selected.y }
    update({ ...flow, nodes: [...flow.nodes, node], edges: [...flow.edges, ...auto] })
    setSelectedId(node.id)
    reveal(node)
  }

  function updateNode(changes: Partial<FlowNode>) {
    if (!flow || !selected) return
    update({ ...flow, nodes: flow.nodes.map((node) => node.id === selected.id ? { ...node, ...changes } : node) })
  }

  function deleteNode() {
    if (!flow || !selected) return
    update({ ...flow, nodes: flow.nodes.filter((node) => node.id !== selected.id), edges: flow.edges.filter((edge) => edge.from !== selected.id && edge.to !== selected.id) })
    setSelectedId("")
  }

  async function ask(prompt: string) {
    const order: ChatTransport[] = transportRef.current ? [transportRef.current] : ["cloud", "local"]
    let lastError: unknown
    for (const transport of order) {
      try {
        const reply = parseChatReply(await chatRequest(transport, "chat", { messages: [{ role: "user", content: prompt.slice(0, 12_000) }] }, abortRef.current?.signal))
        transportRef.current = transport
        return reply.text
      } catch (error) { lastError = error }
    }
    throw new Error(lastError instanceof Error && lastError.name !== "AbortError" ? `IA indisponível: ${lastError.message}` : "IA indisponível. Conecte a IA no KIARA Chat (Ajustes).")
  }

  async function run() {
    if (!flow || running) return
    const controller = new AbortController()
    abortRef.current = controller
    setRunning(true); setRunError(""); setStatuses({}); setSteps([]); setActiveEdges(new Set()); setLogOpen(true)
    if (typeof Notification !== "undefined" && Notification.permission === "default" && flow.nodes.some((node) => node.type === "logic.notify")) void Notification.requestPermission()
    try {
      await runWorkflow(flow, {
        ask, signal: controller.signal,
        onStep: (step) => {
          setStatuses((current) => ({ ...current, [step.nodeId]: step.status }))
          if (step.status === "done") setActiveEdges((current) => new Set([...current, ...flow.edges.filter((edge) => edge.from === step.nodeId).map((edge) => edge.id)]))
          if (step.status !== "running") setSteps((current) => [...current, step])
        },
      })
    } catch (error) {
      setRunError(error instanceof DOMException && error.name === "AbortError" ? "Execução interrompida." : error instanceof Error ? error.message : "A execução falhou.")
    } finally { setRunning(false); abortRef.current = null }
  }

  const needle = search.trim().toLowerCase()
  const groups = (Object.keys(categories) as CategoryId[]).map((category) => ({ category, kinds: nodeKinds.filter((kind) => kind.category === category && (!needle || `${kind.label} ${kind.description} ${categories[category].label}`.toLowerCase().includes(needle))) })).filter((group) => group.kinds.length)
  const blocked = steps.filter((step) => step.status === "blocked").length
  const errors = steps.filter((step) => step.status === "error").length

  const sidebar = (close: () => void) => <div className="space-y-5">
    <Button type="button" variant="ghost" className="w-full justify-start gap-2 px-2" onClick={() => { open(emptyWorkflow()); close() }}><Plus />Novo fluxo</Button>
    <div>
      <p className="flex items-center gap-1.5 px-2 pb-1 text-xs font-medium text-sidebar-foreground/50"><LayoutTemplate className="size-3.5" />Modelos prontos</p>
      <ul className="space-y-0.5">{templates.map((template) => <li key={template.id}><button type="button" onClick={() => { open(template.build()); close() }} className="w-full rounded-lg px-2 py-2 text-left hover:bg-sidebar-foreground/5"><span className="block truncate text-sm">{template.title}</span><span className="block text-xs text-sidebar-foreground/50">{template.description}</span></button></li>)}</ul>
    </div>
    {flows.length ? <div>
      <p className="px-2 pb-1 text-xs font-medium text-sidebar-foreground/50">Meus fluxos</p>
      <ul className="space-y-0.5">{flows.map((item) => <li key={item.id} className="group relative">
        <button type="button" onClick={() => { setActiveId(item.id); setSelectedId(""); setStatuses({}); setSteps([]); close(); requestAnimationFrame(() => fit(item)) }} aria-current={item.id === activeId ? "true" : undefined} className={cn("block w-full truncate rounded-lg px-2 py-2 pr-8 text-left text-sm text-sidebar-foreground/80 hover:bg-sidebar-foreground/5", item.id === activeId && "bg-sidebar-foreground/10 text-sidebar-foreground")}>{item.name}</button>
        <button type="button" onClick={() => remove(item.id)} aria-label={`Excluir ${item.name}`} className="absolute right-1 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-sidebar-foreground/50 opacity-0 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"><Trash2 className="size-3.5" /></button>
      </li>)}</ul>
    </div> : null}
  </div>

  return <ImmersiveShell label="Fluxos da Kiara Automation" sidebar={sidebar}
    footer={<AdminOnly><Link href="/app/settings/integrations" className="flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground"><Plug className="size-4" />Conexões</Link></AdminOnly>}
    topBar={flow ? <>
      <WorkflowIcon className="size-4 shrink-0 text-primary" aria-hidden="true" />
      <input value={flow.name} onChange={(event) => update({ ...flow, name: event.target.value.slice(0, 80) })} aria-label="Nome do fluxo" className="min-w-0 flex-1 truncate bg-transparent text-sm font-medium outline-none" />
      <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:inline-flex"><Check className="size-3.5" />Salvo</span>
      {running ? <Button type="button" size="sm" variant="outline" onClick={() => abortRef.current?.abort()}><Square />Parar</Button>
        : <Button type="button" size="sm" onClick={() => void run()}><Play />Executar</Button>}
    </> : <span className="font-medium">Kiara Automation</span>}>
    {flow ? <div ref={areaRef} className="relative flex min-h-0 flex-1">
      <FlowCanvas workflow={flow} onChange={update} view={view} onViewChange={setView} selectedId={selectedId} onSelect={setSelectedId} statuses={statuses} activeEdges={activeEdges} onDropNode={addNode} />

      <div className="absolute left-3 top-3 z-10 w-64 max-w-[calc(100%-1.5rem)] overflow-hidden rounded-2xl border bg-card/90 shadow-xl backdrop-blur-xl">
        <button type="button" onClick={() => setPaletteOpen(!paletteOpen)} aria-expanded={paletteOpen} className="flex w-full items-center gap-2 px-3 py-2.5 text-sm font-medium"><Plus className="size-4 text-primary" />Adicionar bloco<ChevronDown className={cn("ml-auto size-4 transition-transform", paletteOpen && "rotate-180")} /></button>
        {paletteOpen ? <div className="max-h-[min(60vh,520px)] space-y-3 overflow-y-auto border-t p-3">
          <div className="relative"><Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar bloco" className="h-8 pl-8 text-sm" aria-label="Buscar bloco" /></div>
          {groups.map(({ category, kinds }) => <div key={category}>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: categories[category].color }}>{categories[category].label}</p>
            <ul className="space-y-1">{kinds.map((kind) => <li key={kind.type}>
              <button type="button" draggable onDragStart={(event) => { event.dataTransfer.setData(NODE_DRAG_TYPE, kind.type); event.dataTransfer.effectAllowed = "copy" }} onClick={() => addNode(kind.type)} title={kind.description}
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-muted/60" style={{ "--accent-color": categories[category].color } as CSSProperties}>
                <span className="grid size-6 shrink-0 place-items-center rounded-md" style={{ background: `color-mix(in oklab, ${categories[category].color} 18%, transparent)`, color: categories[category].color }}><NodeIcon name={kind.icon} className="size-3.5" /></span>
                <span className="min-w-0 flex-1 truncate">{kind.label}</span>
                {kind.run !== "browser" ? <Plug className="size-3 shrink-0 text-amber-400" aria-label="Precisa conectar" /> : null}
              </button>
            </li>)}</ul>
          </div>)}
        </div> : null}
      </div>

      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-1 rounded-xl border bg-card/90 p-1 shadow-lg backdrop-blur-xl">
        <Button type="button" variant="ghost" size="icon" className="size-8" aria-label="Diminuir zoom" onClick={() => setView({ ...view, zoom: Math.max(0.3, view.zoom * 0.85) })}><ZoomOut /></Button>
        <span className="w-11 text-center text-xs tabular-nums text-muted-foreground">{Math.round(view.zoom * 100)}%</span>
        <Button type="button" variant="ghost" size="icon" className="size-8" aria-label="Aumentar zoom" onClick={() => setView({ ...view, zoom: Math.min(2, view.zoom * 1.15) })}><ZoomIn /></Button>
        <Button type="button" variant="ghost" size="icon" className="size-8" aria-label="Enquadrar fluxo" onClick={() => fit()}><Maximize2 /></Button>
      </div>

      {steps.length || running || runError ? <section aria-label="Execução" className="absolute bottom-3 left-1/2 z-10 w-[min(560px,calc(100%-1.5rem))] -translate-x-1/2 overflow-hidden rounded-2xl border bg-card/95 shadow-2xl backdrop-blur-xl">
        <button type="button" onClick={() => setLogOpen(!logOpen)} className="flex w-full items-center gap-2 px-4 py-2.5 text-sm" aria-expanded={logOpen}>
          {running ? <LoaderCircle className="size-4 animate-spin text-primary" /> : runError || errors ? <CircleAlert className="size-4 text-destructive" /> : <Check className="size-4 text-emerald-400" />}
          <span className="font-medium">{running ? "Executando…" : runError || (errors ? `${errors} bloco(s) com erro` : blocked ? `Concluído · ${blocked} bloco(s) precisam de conexão` : "Execução concluída")}</span>
          <ChevronDown className={cn("ml-auto size-4 transition-transform", logOpen && "rotate-180")} />
        </button>
        {logOpen ? <ol className="max-h-64 space-y-2 overflow-y-auto border-t p-3">{steps.map((step, index) => {
          const kind = nodeKind(flow.nodes.find((node) => node.id === step.nodeId)?.type ?? "")
          return <li key={`${step.nodeId}-${index}`} className="rounded-lg bg-muted/30 p-2.5 text-sm">
            <p className="flex items-center gap-2"><span className={cn("size-1.5 rounded-full", step.status === "done" ? "bg-emerald-400" : step.status === "blocked" ? "bg-amber-400" : "bg-destructive")} /><button type="button" className="font-medium hover:underline" onClick={() => setSelectedId(step.nodeId)}>{kind?.label ?? "Bloco"}</button><span className="text-xs text-muted-foreground">{statusLabels[step.status]}</span></p>
            {step.message ? <p className="mt-1 text-xs text-muted-foreground">{step.message}</p> : null}
            {step.output ? <p className="mt-1 line-clamp-6 whitespace-pre-wrap break-words text-xs">{step.output}</p> : null}
          </li>
        })}</ol> : null}
      </section> : null}

      {selected && selectedKind ? <aside aria-label="Ajustes do bloco" className="absolute inset-y-3 right-3 z-20 flex w-[min(340px,calc(100%-1.5rem))] flex-col overflow-hidden rounded-2xl border bg-card/95 shadow-2xl backdrop-blur-xl">
        <header className="flex items-start gap-3 border-b p-4" style={{ "--accent-color": categories[selectedKind.category].color } as CSSProperties}>
          <span className="grid size-9 shrink-0 place-items-center rounded-xl" style={{ background: `color-mix(in oklab, ${categories[selectedKind.category].color} 18%, transparent)`, color: categories[selectedKind.category].color }}><NodeIcon name={selectedKind.icon} className="size-4" /></span>
          <div className="min-w-0 flex-1"><h2 className="font-semibold">{selectedKind.label}</h2><p className="text-xs text-muted-foreground">{categories[selectedKind.category].label}</p></div>
          <Button type="button" variant="ghost" size="icon" className="size-8" aria-label="Fechar ajustes" onClick={() => setSelectedId("")}><X /></Button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          <p className="text-sm text-muted-foreground">{selectedKind.description}</p>
          {selectedKind.run === "browser"
            ? <p className="flex items-center gap-2 rounded-lg bg-emerald-400/10 px-3 py-2 text-xs text-emerald-400"><Check className="size-3.5" />Funciona agora, direto nesta página.</p>
            : <div className="rounded-lg bg-amber-400/10 px-3 py-2 text-xs text-amber-300"><p className="flex items-center gap-2 font-medium"><Plug className="size-3.5" />Precisa conectar</p><p className="mt-1">{connectionLabels[selectedKind.run]}. Ao executar sem a conexão, o fluxo para neste bloco e avisa; nada é simulado.</p><AdminOnly><Link href="/app/settings/integrations" className="mt-1 inline-block underline">Abrir conexões</Link></AdminOnly></div>}
          {selectedKind.fields.map((field) => {
            const id = `field-${selected.id}-${field.key}`
            const value = selected.config[field.key] ?? ""
            const set = (next: string | number) => updateNode({ config: { ...selected.config, [field.key]: next } })
            return <div key={field.key} className="space-y-1.5">
              <label htmlFor={id} className="text-sm font-medium">{field.label}</label>
              {field.type === "textarea" ? <Textarea id={id} value={String(value)} onChange={(event) => set(event.target.value)} placeholder={field.placeholder} className={field.key === "code" ? "min-h-32 font-mono text-xs" : "min-h-24"} />
                : field.type === "select" ? <select id={id} value={String(value)} onChange={(event) => set(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{field.options!.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
                  : <Input id={id} type={field.type === "number" ? "number" : field.type === "time" ? "time" : "text"} min={field.min} max={field.max} value={String(value)} placeholder={field.placeholder} onChange={(event) => set(field.type === "number" ? Number(event.target.value) : event.target.value)} />}
              {field.hint ? <p className="text-xs text-muted-foreground">{field.hint}</p> : null}
            </div>
          })}
          {selectedKind.ads ? <AdsCost kind={selectedKind} node={selected} /> : null}
          {selectedKind.fields.some((field) => String(selected.config[field.key] ?? "").includes("{{entrada}}") || field.placeholder?.includes("{{entrada}}")) ? <p className="text-xs text-muted-foreground">Dica: <code>{"{{entrada}}"}</code> é substituído pelo resultado do bloco anterior.</p> : null}
        </div>
        <footer className="flex gap-2 border-t p-3">
          <Button type="button" variant="outline" size="sm" onClick={() => { if (!flow) return; const copy = { ...selected, id: newId("n"), x: selected.x + 40, y: selected.y + 90 }; update({ ...flow, nodes: [...flow.nodes, copy] }); setSelectedId(copy.id) }}><Copy />Duplicar</Button>
          <Button type="button" variant="outline" size="sm" className="ml-auto text-destructive" onClick={deleteNode}><Trash2 />Excluir</Button>
        </footer>
      </aside> : null}
    </div> : <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <span className="mb-4 grid size-14 place-items-center rounded-2xl border bg-card text-primary"><WorkflowIcon className="size-6" /></span>
      <h1 className="text-2xl font-medium tracking-tight">Automatize com a Kiara</h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">Monte fluxos ligando blocos: gatilhos, IA, CRM, mensagens, agenda, sites, computador, redes sociais e anúncios.</p>
      <div className="mt-6 grid w-full max-w-2xl gap-3 sm:grid-cols-2">{templates.map((template) => <button key={template.id} type="button" onClick={() => open(template.build())} className="rounded-2xl border bg-card p-4 text-left transition hover:border-primary/50"><p className="font-medium">{template.title}</p><p className="mt-1 text-sm text-muted-foreground">{template.description}</p></button>)}</div>
      <Button type="button" variant="outline" className="mt-4" onClick={() => open(emptyWorkflow())}><Plus />Começar do zero</Button>
    </div>}
  </ImmersiveShell>
}
