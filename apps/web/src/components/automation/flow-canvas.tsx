"use client"

import { useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react"
import { BellRing as Bell, Box, BrainCircuit, Briefcase, Building2, CalendarClock, CalendarPlus, Camera, Code, FolderSync, GitBranch, Globe, Mail, MapPin, Megaphone, MessageCircle, Monitor, MousePointerClick, Play, Search, Send, Sparkles, ThumbsUp, Timer, UserPlus, Users, X, type LucideIcon } from "lucide-react"
import { categories, newId, nodeKind, type FlowEdge, type FlowNode, type Workflow } from "@/lib/automation/catalog"
import type { StepStatus } from "@/lib/automation/runner"
import { cn } from "@/lib/utils"
import styles from "./flow.module.css"

export const NODE_WIDTH = 232
export const NODE_HEIGHT = 64
export type View = { x: number; y: number; zoom: number }
export const NODE_DRAG_TYPE = "application/x-kiara-node"

type Port = "out" | "yes" | "no"
type Drag =
  | { mode: "pan"; startX: number; startY: number; origin: View }
  | { mode: "node"; id: string; startX: number; startY: number; originX: number; originY: number; moved: boolean }
  | { mode: "connect"; from: string; port: Port }

// Only the icons the catalog uses, so the editor does not ship the whole icon set.
const icons: Record<string, LucideIcon> = { Bell, BrainCircuit, Briefcase, Building2, CalendarClock, CalendarPlus, Camera, Code, FolderSync, GitBranch, Globe, Mail, MapPin, Megaphone, MessageCircle, Monitor, MousePointerClick, Play, Search, Send, Sparkles, ThumbsUp, Timer, UserPlus, Users }

export function NodeIcon({ name, className }: { name: string; className?: string }) {
  const Icon = icons[name] ?? Box
  return <Icon className={className} aria-hidden="true" />
}

function portPoint(node: FlowNode, port: Port | "in") {
  if (port === "in") return { x: node.x, y: node.y + NODE_HEIGHT / 2 }
  const y = port === "yes" ? node.y + NODE_HEIGHT * 0.35 : port === "no" ? node.y + NODE_HEIGHT * 0.72 : node.y + NODE_HEIGHT / 2
  return { x: node.x + NODE_WIDTH, y }
}

function curve(a: { x: number; y: number }, b: { x: number; y: number }) {
  const dx = Math.max(60, Math.abs(b.x - a.x) / 2)
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`
}

/** Node-and-wire editor: pan, wheel zoom, drag nodes, wire output → input, drop blocks from the palette. */
export function FlowCanvas({ workflow, onChange, view, onViewChange, selectedId, onSelect, statuses, activeEdges, onDropNode }: {
  workflow: Workflow
  onChange: (workflow: Workflow) => void
  view: View
  onViewChange: (view: View) => void
  selectedId: string
  onSelect: (id: string) => void
  statuses: Record<string, StepStatus>
  activeEdges: Set<string>
  onDropNode: (type: string, at: { x: number; y: number }) => void
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<Drag | null>(null)
  const [draft, setDraft] = useState<{ from: { x: number; y: number }; to: { x: number; y: number } } | null>(null)
  const [selectedEdge, setSelectedEdge] = useState("")
  const [panning, setPanning] = useState(false)

  function toWorld(clientX: number, clientY: number) {
    const rect = rootRef.current!.getBoundingClientRect()
    return { x: (clientX - rect.left - view.x) / view.zoom, y: (clientY - rect.top - view.y) / view.zoom }
  }

  function startPan(event: ReactPointerEvent) {
    if (event.button !== 0) return
    rootRef.current?.setPointerCapture(event.pointerId)
    dragRef.current = { mode: "pan", startX: event.clientX, startY: event.clientY, origin: view }
    setPanning(true); setSelectedEdge(""); onSelect("")
  }

  function startNode(event: ReactPointerEvent, node: FlowNode) {
    event.stopPropagation()
    if (event.button !== 0) return
    rootRef.current?.setPointerCapture(event.pointerId)
    dragRef.current = { mode: "node", id: node.id, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y, moved: false }
    onSelect(node.id); setSelectedEdge("")
  }

  function startConnect(event: ReactPointerEvent, node: FlowNode, port: Port) {
    event.stopPropagation()
    rootRef.current?.setPointerCapture(event.pointerId)
    dragRef.current = { mode: "connect", from: node.id, port }
    const from = portPoint(node, port)
    setDraft({ from, to: from })
  }

  function move(event: ReactPointerEvent) {
    const drag = dragRef.current
    if (!drag) return
    if (drag.mode === "pan") onViewChange({ ...drag.origin, x: drag.origin.x + event.clientX - drag.startX, y: drag.origin.y + event.clientY - drag.startY })
    else if (drag.mode === "node") {
      const dx = (event.clientX - drag.startX) / view.zoom, dy = (event.clientY - drag.startY) / view.zoom
      if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true
      onChange({ ...workflow, nodes: workflow.nodes.map((node) => node.id === drag.id ? { ...node, x: Math.round(drag.originX + dx), y: Math.round(drag.originY + dy) } : node) })
    } else setDraft((current) => current ? { ...current, to: toWorld(event.clientX, event.clientY) } : current)
  }

  function end(event: ReactPointerEvent) {
    const drag = dragRef.current
    dragRef.current = null
    setPanning(false)
    if (drag?.mode !== "connect") return
    setDraft(null)
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-node-id]")
    const to = target?.dataset.nodeId
    if (!to || to === drag.from || nodeKind(workflow.nodes.find((node) => node.id === to)?.type ?? "")?.trigger) return
    const port = drag.port === "out" ? undefined : drag.port
    if (workflow.edges.some((edge) => edge.from === drag.from && edge.to === to && edge.port === port)) return
    const edge: FlowEdge = { id: newId("e"), from: drag.from, to, ...(port ? { port } : {}) }
    onChange({ ...workflow, edges: [...workflow.edges, edge] })
  }

  function wheel(event: React.WheelEvent) {
    const rect = rootRef.current!.getBoundingClientRect()
    const zoom = Math.min(2, Math.max(0.3, view.zoom * (event.deltaY > 0 ? 0.9 : 1.1)))
    const px = event.clientX - rect.left, py = event.clientY - rect.top
    onViewChange({ zoom, x: px - ((px - view.x) / view.zoom) * zoom, y: py - ((py - view.y) / view.zoom) * zoom })
  }

  const byId = new Map(workflow.nodes.map((node) => [node.id, node]))
  const edgeGeometry = workflow.edges.flatMap((edge) => {
    const from = byId.get(edge.from), to = byId.get(edge.to)
    if (!from || !to) return []
    const a = portPoint(from, edge.port ?? (nodeKind(from.type)?.branches ? "yes" : "out")), b = portPoint(to, "in")
    return [{ edge, d: curve(a, b), mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 } }]
  })
  const deletable = edgeGeometry.find((item) => item.edge.id === selectedEdge)

  return <div ref={rootRef} className={cn(styles.canvas, panning && styles.panning)} style={{ backgroundSize: `${22 * view.zoom}px ${22 * view.zoom}px`, backgroundPosition: `${view.x}px ${view.y}px` }}
    onPointerDown={startPan} onPointerMove={move} onPointerUp={end} onPointerCancel={end} onWheel={wheel}
    onDragOver={(event) => { if (event.dataTransfer.types.includes(NODE_DRAG_TYPE)) event.preventDefault() }}
    onDrop={(event) => { const type = event.dataTransfer.getData(NODE_DRAG_TYPE); if (type) { event.preventDefault(); const at = toWorld(event.clientX, event.clientY); onDropNode(type, { x: at.x - NODE_WIDTH / 2, y: at.y - NODE_HEIGHT / 2 }) } }}
    role="application" aria-label="Editor de fluxo: arraste para mover a tela, use a roda do mouse para zoom">
    <div className={styles.world} style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom})` }}>
      <svg className={styles.edges} width="1" height="1">
        <defs><filter id="flow-comet-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" /></filter></defs>
        {edgeGeometry.map(({ edge, d }) => {
          const done = statuses[edge.to] === "done" || statuses[edge.to] === "blocked"
          return <path key={edge.id} d={d} className={cn(styles.edge, activeEdges.has(edge.id) && styles.edgeActive, done && !activeEdges.has(edge.id) && styles.edgeDone)} onPointerDown={(event) => { event.stopPropagation(); setSelectedEdge(edge.id); onSelect("") }} />
        })}
        {/* Energy running through the wires that are executing right now. */}
        {edgeGeometry.filter(({ edge }) => activeEdges.has(edge.id)).map(({ edge, d }) => <g key={`comet-${edge.id}`} className={styles.comet} aria-hidden="true">
          <circle r="9" fill="var(--primary)" opacity=".55" filter="url(#flow-comet-glow)"><animateMotion dur="0.9s" repeatCount="indefinite" path={d} /></circle>
          <circle r="3.5" fill="#fff"><animateMotion dur="0.9s" repeatCount="indefinite" path={d} /></circle>
        </g>)}
        {draft ? <path d={curve(draft.from, draft.to)} className={styles.edgeDraft} /> : null}
      </svg>
      {deletable ? <button type="button" className={styles.edgeDelete} style={{ left: deletable.mid.x, top: deletable.mid.y }} aria-label="Remover conexão" onPointerDown={(event) => event.stopPropagation()} onClick={() => { onChange({ ...workflow, edges: workflow.edges.filter((edge) => edge.id !== selectedEdge) }); setSelectedEdge("") }}><X className="size-3" /></button> : null}
      {workflow.nodes.map((node) => {
        const kind = nodeKind(node.type)
        if (!kind) return null
        const status = statuses[node.id]
        return <div key={node.id} data-node-id={node.id} className={cn(styles.node, node.id === selectedId && styles.selected, status && styles[status])}
          style={{ left: node.x, top: node.y, height: NODE_HEIGHT, "--accent-color": categories[kind.category].color } as CSSProperties}
          onPointerDown={(event) => startNode(event, node)} role="button" tabIndex={0} aria-label={`${kind.label}${status ? `, ${status}` : ""}`}
          onKeyDown={(event) => { if (event.key === "Enter") onSelect(node.id) }}>
          {kind.run !== "browser" ? <span className={cn(styles.badge, styles.badgeNeeds)}>Conectar</span> : null}
          {!kind.trigger ? <span className={cn(styles.port, styles.portIn)} aria-hidden="true" /> : null}
          <div className={styles.nodeBody}>
            <span className={styles.icon}><NodeIcon name={kind.icon} /></span>
            <div className="min-w-0"><p className={styles.title}>{kind.label}</p><p className={styles.subtitle}>{categories[kind.category].label}</p></div>
          </div>
          {kind.branches ? <>
            <span className={cn(styles.port, styles.portOut, styles.portYes)} onPointerDown={(event) => startConnect(event, node, "yes")} aria-label="Saída Sim" />
            <span className={styles.portLabel} style={{ top: "35%" }}>Sim</span>
            <span className={cn(styles.port, styles.portOut, styles.portNo)} onPointerDown={(event) => startConnect(event, node, "no")} aria-label="Saída Não" />
            <span className={styles.portLabel} style={{ top: "72%" }}>Não</span>
          </> : <span className={cn(styles.port, styles.portOut)} onPointerDown={(event) => startConnect(event, node, "out")} aria-label="Saída" />}
        </div>
      })}
    </div>
  </div>
}
