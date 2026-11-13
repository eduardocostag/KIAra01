"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import type { GeoJSONSource, Map as MapLibreMap, Popup } from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
import { bounds, columnHeight, hexagon, temperatureColors, type LngLat, type Temperature } from "@/lib/lead-geo"
import { prefersReducedMotion } from "@/components/fx/fx"
import styles from "./lead-map.module.css"

export type MapLead = { id: string; name: string; at: LngLat; temperature: Temperature; score: number | null }

const STYLE_URL = "https://tiles.openfreemap.org/styles/dark"
const WORKER_URL = "/vendor/maplibre-gl-worker.mjs"
const BRAZIL: LngLat = [-51.9253, -14.235]
const PINGS = [[-18, 22], [26, -14], [-30, -26], [12, 30], [34, 18], [-6, -34]] as const
const pingColors = ["#fb7185", "#fbbf24", "#38bdf8", "#a78bfa", "#34d399", "#fb7185"]

type Feature = GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.Point, Record<string, string | number>>

function collection(features: Feature[]): GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.Point> {
  return { type: "FeatureCollection", features }
}

/**
 * 3D map of the search. While searching: a dark globe spins under a radar sweep.
 * With results: the camera flies from the globe to the city, buildings rise in 3D and every
 * lead becomes a light column (color = temperature, height = lead score). Click a column to jump
 * to the lead in the list.
 */
export default function LeadMap3D({ scanning, leads, total, query, location, onSelect, onUnavailable }: {
  scanning: boolean
  leads: MapLead[]
  total: number
  query?: string
  location?: string | null
  onSelect?: (id: string) => void
  onUnavailable?: () => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)
  const spinRef = useRef(0)
  const revealRef = useRef(0)
  const popupRef = useRef<Popup | null>(null)
  const selectRef = useRef(onSelect)
  const unavailableRef = useRef(onUnavailable)
  useEffect(() => { selectRef.current = onSelect; unavailableRef.current = onUnavailable })

  // Build the map once.
  useEffect(() => {
    let cancelled = false
    let map: MapLibreMap | null = null
    void import("maplibre-gl").then(({ Map, Popup, setWorkerUrl }) => {
      if (cancelled || !containerRef.current) return
      // Bundlers move the library away from its worker file; serve the worker from /public (same version).
      setWorkerUrl(WORKER_URL)
      try {
        map = new Map({
          container: containerRef.current, style: STYLE_URL, center: BRAZIL, zoom: 1.6, pitch: 0,
          attributionControl: { compact: true }, canvasContextAttributes: { antialias: true }, maxPitch: 75,
        })
      } catch {
        unavailableRef.current?.()
        return
      }
      mapRef.current = map
      popupRef.current = new Popup({ closeButton: false, closeOnClick: false, offset: 12 })
      map.on("error", () => { /* tile hiccups are not fatal */ })
      map.on("style.load", () => {
        if (!map) return
        map.setProjection({ type: "globe" })
        map.setSky({ "sky-color": "#120d26", "horizon-color": "#3b1f74", "fog-color": "#0b0a14", "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 8, .6, 12, 0] })
        map.addLayer({
          id: "kiara-buildings", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building", minzoom: 12.5,
          paint: {
            "fill-extrusion-color": "#2b2545",
            "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
            "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
            "fill-extrusion-opacity": .82,
          },
        })
        map.addSource("lead-columns", { type: "geojson", data: collection([]) })
        map.addSource("lead-points", { type: "geojson", data: collection([]) })
        map.addLayer({ id: "lead-glow", type: "circle", source: "lead-points", paint: { "circle-color": ["get", "color"], "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 4, 12, 18, 16, 40], "circle-blur": 1, "circle-opacity": .55 } })
        map.addLayer({ id: "lead-columns", type: "fill-extrusion", source: "lead-columns", paint: { "fill-extrusion-color": ["get", "color"], "fill-extrusion-height": ["get", "h"], "fill-extrusion-base": 0, "fill-extrusion-opacity": .92 } })
        map.on("mousemove", "lead-columns", (event) => {
          const feature = event.features?.[0]
          if (!map || !feature) return
          map.getCanvas().style.cursor = "pointer"
          popupRef.current?.setLngLat(event.lngLat).setText(String(feature.properties?.name ?? "")).addTo(map)
        })
        map.on("mouseleave", "lead-columns", () => { if (map) map.getCanvas().style.cursor = ""; popupRef.current?.remove() })
        map.on("click", "lead-columns", (event) => { const id = event.features?.[0]?.properties?.id; if (id) selectRef.current?.(String(id)) })
        setReady(true)
      })
      // Any user gesture stops the automatic camera motion.
      for (const type of ["mousedown", "touchstart", "wheel"] as const) map.on(type, () => { cancelAnimationFrame(spinRef.current); spinRef.current = -1 })
    }).catch(() => unavailableRef.current?.())
    return () => {
      cancelled = true
      cancelAnimationFrame(spinRef.current); cancelAnimationFrame(revealRef.current)
      popupRef.current?.remove()
      map?.remove(); mapRef.current = null
    }
  }, [])

  const target = useMemo(() => {
    const points = leads.map((lead) => lead.at)
    const box = bounds(points)
    if (!box) return null
    const diagonal = Math.hypot((box[1][0] - box[0][0]) * 111_320 * Math.cos((box[0][1] * Math.PI) / 180), (box[1][1] - box[0][1]) * 111_320)
    const radius = Math.max(30, Math.min(420, diagonal / 85))
    return { box, radius, scale: Math.max(.7, Math.min(2.6, radius / 60)) }
  }, [leads])

  // Searching: slow globe spin. Results: fly to the city and raise the columns one by one.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const reduced = prefersReducedMotion()
    cancelAnimationFrame(spinRef.current); cancelAnimationFrame(revealRef.current)
    const columns = map.getSource<GeoJSONSource>("lead-columns")
    const points = map.getSource<GeoJSONSource>("lead-points")

    function spin() {
      if (!map || spinRef.current === -1) return
      const center = map.getCenter()
      map.setCenter([center.lng + .12, center.lat])
      spinRef.current = requestAnimationFrame(spin)
    }

    if (scanning || !target) {
      columns?.setData(collection([])); points?.setData(collection([]))
      map.easeTo({ center: BRAZIL, zoom: 1.6, pitch: 0, bearing: 0, duration: reduced ? 0 : 1600 })
      if (!reduced) { spinRef.current = 0; map.once("moveend", () => { if (spinRef.current !== -1) spinRef.current = requestAnimationFrame(spin) }) }
      return
    }

    spinRef.current = 0
    const features = (progress: (index: number) => number): Feature[] => leads.map((lead, index) => ({
      type: "Feature", id: index,
      geometry: { type: "Polygon", coordinates: [hexagon(lead.at, target.radius)] },
      properties: { id: lead.id, name: lead.name, color: temperatureColors[lead.temperature], h: columnHeight(lead.score, target.scale) * progress(index) },
    }))
    points?.setData(collection(leads.map((lead) => ({ type: "Feature", geometry: { type: "Point", coordinates: lead.at }, properties: { color: temperatureColors[lead.temperature] } }))))
    columns?.setData(collection(features(() => reduced ? 1 : 0)))

    const single = leads.length === 1
    const camera = single
      ? { center: leads[0].at, zoom: 15.5 }
      : map.cameraForBounds(target.box, { padding: { top: 70, bottom: 60, left: 50, right: 50 }, maxZoom: 15.5 })
    map.flyTo({ ...camera, pitch: 58, bearing: -18, duration: reduced ? 0 : 3200, essential: true, curve: 1.6 })

    if (reduced) return
    map.once("moveend", () => {
      const started = performance.now()
      const rise = (now: number) => {
        const elapsed = now - started
        const ease = (index: number) => { const t = Math.max(0, Math.min(1, (elapsed - index * 70) / 900)); return 1 - Math.pow(1 - t, 3) }
        columns?.setData(collection(features(ease)))
        if (elapsed < leads.length * 70 + 950) revealRef.current = requestAnimationFrame(rise)
        else if (spinRef.current !== -1) orbit()
      }
      revealRef.current = requestAnimationFrame(rise)
    })
    // After the reveal the camera keeps a slow orbit until the user takes over.
    function orbit() {
      if (!map || spinRef.current === -1) return
      map.setBearing(map.getBearing() + .04)
      spinRef.current = requestAnimationFrame(orbit)
    }
  }, [ready, scanning, target, leads])

  const counts = { hot: 0, warm: 0, cold: 0 }
  for (const lead of leads) counts[lead.temperature] += 1

  return <div className={styles.frame}>
    <div ref={containerRef} className={styles.map} aria-label={scanning ? "Mapa: buscando leads" : `Mapa com ${leads.length} leads`} role="img" />
    {scanning ? <div className={styles.radar} aria-hidden="true">
      {PINGS.map(([x, y], index) => <span key={index} className={styles.ping} style={{ left: `calc(50% + ${x * 4}px)`, top: `calc(50% + ${y * 4}px)`, animationDelay: `${index * .43}s`, ["--ping" as string]: pingColors[index] }} />)}
    </div> : null}
    <div className={styles.hud}>
      <strong>{scanning ? "Varrendo as fontes…" : leads.length ? `${leads.length} lead${leads.length === 1 ? "" : "s"} no mapa` : "Mapa dos leads"}</strong>
      <span>{scanning ? `${query || "Busca"}${location ? ` · ${location}` : ""}` : total > leads.length ? `${total - leads.length} sem coordenada aparecem só na lista` : "Clique numa coluna para ver o lead"}</span>
    </div>
    {!scanning && leads.length ? <div className={styles.legend} aria-hidden="true">
      <span><i style={{ background: temperatureColors.hot }} />Quente {counts.hot}</span>
      <span><i style={{ background: temperatureColors.warm }} />Morno {counts.warm}</span>
      <span><i style={{ background: temperatureColors.cold }} />Frio {counts.cold}</span>
      <span>altura = nota</span>
    </div> : null}
  </div>
}
