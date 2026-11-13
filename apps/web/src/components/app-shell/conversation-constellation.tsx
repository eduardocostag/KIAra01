"use client"

import { useEffect, useMemo, useRef, useState } from "react"

export type Star = { id: string; name: string; unread: number; temperature: string; score: number }

const colors: Record<string, string> = { hot: "#fb7185", warm: "#fbbf24", cold: "#38bdf8", unknown: "#a78bfa" }
const GOLDEN = Math.PI * (3 - Math.sqrt(5))

/**
 * Every conversation is a star: brighter and bigger = better lead score, color = temperature.
 * Conversations with unread messages pulse and receive comets. Click a star to open it.
 */
export function ConversationConstellation({ stars, activeId, onPick }: { stars: Star[]; activeId?: string; onPick: (id: string) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hover, setHover] = useState<{ star: Star; x: number; y: number } | null>(null)
  // Most recent conversations near the center, on a sunflower spiral so they never overlap.
  const layout = useMemo(() => stars.map((star, index) => {
    const radius = Math.sqrt((index + .6) / Math.max(stars.length, 1)) * .42
    const angle = index * GOLDEN
    return { star, x: .5 + Math.cos(angle) * radius, y: .5 + Math.sin(angle) * radius * .78, size: 2.2 + (star.score / 100) * 4.5, color: colors[star.temperature] ?? colors.unknown }
  }), [stars])
  const pointsRef = useRef(layout)
  useEffect(() => { pointsRef.current = layout }, [layout])

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext("2d")
    if (!canvas || !context) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const dust = Array.from({ length: 90 }, () => ({ x: Math.random(), y: Math.random(), r: Math.random() * 1.1, t: Math.random() * 6 }))
    const comets: { from: [number, number]; to: number; born: number }[] = []
    let frame = 0, lastComet = 0
    function draw(now: number) {
      const ratio = Math.min(2, window.devicePixelRatio || 1)
      const width = canvas!.clientWidth, height = canvas!.clientHeight
      if (canvas!.width !== Math.round(width * ratio)) { canvas!.width = Math.round(width * ratio); canvas!.height = Math.round(height * ratio) }
      context!.setTransform(ratio, 0, 0, ratio, 0, 0)
      context!.clearRect(0, 0, width, height)
      const time = now / 1000
      for (const speck of dust) {
        context!.globalAlpha = .25 + .25 * Math.sin(time * .8 + speck.t)
        context!.fillStyle = "#fff"
        context!.beginPath(); context!.arc(speck.x * width, speck.y * height, speck.r, 0, Math.PI * 2); context!.fill()
      }
      const points = pointsRef.current
      // Faint lines between neighbours make it read as a constellation.
      context!.globalAlpha = .12; context!.strokeStyle = "#a78bfa"; context!.lineWidth = 1
      for (let index = 1; index < points.length; index += 1) {
        const a = points[index - 1], b = points[index]
        context!.beginPath(); context!.moveTo(a.x * width, a.y * height); context!.lineTo(b.x * width, b.y * height); context!.stroke()
      }
      const unread = points.map((point, index) => ({ point, index })).filter(({ point }) => point.star.unread > 0)
      if (!reduced && unread.length && now - lastComet > 900) {
        lastComet = now
        const target = unread[Math.floor(Math.random() * unread.length)].index
        const edge = Math.random() * Math.PI * 2
        comets.push({ from: [.5 + Math.cos(edge) * .75, .5 + Math.sin(edge) * .75], to: target, born: now })
      }
      for (let index = comets.length - 1; index >= 0; index -= 1) {
        const comet = comets[index]
        const target = points[comet.to]
        const progress = (now - comet.born) / 1100
        if (!target || progress >= 1) { comets.splice(index, 1); continue }
        const ease = 1 - Math.pow(1 - progress, 2)
        const x = (comet.from[0] + (target.x - comet.from[0]) * ease) * width, y = (comet.from[1] + (target.y - comet.from[1]) * ease) * height
        const tailX = (comet.from[0] + (target.x - comet.from[0]) * Math.max(0, ease - .18)) * width, tailY = (comet.from[1] + (target.y - comet.from[1]) * Math.max(0, ease - .18)) * height
        const gradient = context!.createLinearGradient(tailX, tailY, x, y)
        gradient.addColorStop(0, "rgba(52,211,153,0)"); gradient.addColorStop(1, "rgba(52,211,153,.9)")
        context!.globalAlpha = 1; context!.strokeStyle = gradient; context!.lineWidth = 2
        context!.beginPath(); context!.moveTo(tailX, tailY); context!.lineTo(x, y); context!.stroke()
      }
      for (const point of points) {
        const x = point.x * width, y = point.y * height
        const pulse = point.star.unread > 0 && !reduced ? 1 + .35 * Math.sin(time * 4) : 1
        const glow = context!.createRadialGradient(x, y, 0, x, y, point.size * 5 * pulse)
        glow.addColorStop(0, point.color); glow.addColorStop(1, "transparent")
        context!.globalAlpha = point.star.id === activeId ? .9 : .55
        context!.fillStyle = glow
        context!.beginPath(); context!.arc(x, y, point.size * 5 * pulse, 0, Math.PI * 2); context!.fill()
        context!.globalAlpha = 1; context!.fillStyle = "#fff"
        context!.beginPath(); context!.arc(x, y, point.size * .55, 0, Math.PI * 2); context!.fill()
        if (point.star.id === activeId) {
          context!.strokeStyle = point.color; context!.lineWidth = 1.5
          context!.beginPath(); context!.arc(x, y, point.size * 2.6, 0, Math.PI * 2); context!.stroke()
        }
      }
      context!.globalAlpha = 1
      if (!reduced) frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [activeId])

  function nearest(clientX: number, clientY: number) {
    const box = canvasRef.current!.getBoundingClientRect()
    let best: (typeof layout)[number] | null = null, distance = 22
    for (const point of layout) {
      const d = Math.hypot(point.x * box.width - (clientX - box.left), point.y * box.height - (clientY - box.top))
      if (d < distance) { distance = d; best = point }
    }
    return best ? { star: best.star, x: best.x * box.width, y: best.y * box.height } : null
  }

  return <div className="relative h-[min(60vh,460px)] overflow-hidden rounded-2xl border bg-[radial-gradient(ellipse_at_center,#1d1238_0%,#09080f_70%)]">
    <canvas ref={canvasRef} className="absolute inset-0 size-full cursor-crosshair" aria-hidden="true"
      onPointerMove={(event) => setHover(nearest(event.clientX, event.clientY))} onPointerLeave={() => setHover(null)}
      onClick={(event) => { const hit = nearest(event.clientX, event.clientY); if (hit) onPick(hit.star.id) }} />
    {hover ? <div className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[calc(100%+14px)] rounded-lg border border-white/10 bg-black/80 px-2.5 py-1.5 text-xs text-white backdrop-blur" style={{ left: hover.x, top: hover.y }}>
      <p className="font-medium">{hover.star.name}</p>
      <p className="text-white/60">{hover.star.unread ? `${hover.star.unread} não lida(s) · ` : ""}nota {hover.star.score}</p>
    </div> : null}
    {/* Same conversations as a list, for keyboards and screen readers. */}
    <ul className="sr-only">{stars.map((star) => <li key={star.id}><button type="button" onClick={() => onPick(star.id)}>{star.name}{star.unread ? `, ${star.unread} não lidas` : ""}</button></li>)}</ul>
    <p className="pointer-events-none absolute bottom-3 left-3 text-[11px] text-white/55">Tamanho = nota · cor = temperatura · cometas = mensagens novas</p>
  </div>
}
