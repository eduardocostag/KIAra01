/** Coordinates and 3D column geometry for plotting Hunter leads on the map. */

export type LngLat = [number, number]
export type Temperature = "hot" | "warm" | "cold"

export const temperatureColors: Record<Temperature, string> = { hot: "#fb7185", warm: "#fbbf24", cold: "#38bdf8" }

function valid(lat: number, lng: number) {
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 && !(lat === 0 && lng === 0)
}

/**
 * Google Maps place links carry the pin as `!3d<lat>!4d<lng>`; search/view links as `@lat,lng,zoom`.
 * The pin wins because `@` is the camera, which can be offset from the business.
 */
export function coordinatesFromMapsUrl(url: string | null | undefined): LngLat | null {
  if (!url) return null
  let text = url
  try { text = decodeURIComponent(url) } catch { /* keep the raw text */ }
  const pin = text.match(/!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)/)
  if (pin && valid(Number(pin[1]), Number(pin[2]))) return [Number(pin[2]), Number(pin[1])]
  const camera = text.match(/@(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)/)
  if (camera && valid(Number(camera[1]), Number(camera[2]))) return [Number(camera[2]), Number(camera[1])]
  return null
}

/** Hexagon around a point, `radius` in meters: the footprint of a lead's light column. */
export function hexagon([lng, lat]: LngLat, radius: number): LngLat[] {
  const dLat = radius / 111_320
  const dLng = radius / (111_320 * Math.cos((lat * Math.PI) / 180))
  const ring: LngLat[] = []
  for (let side = 0; side <= 6; side += 1) {
    const angle = (Math.PI / 3) * (side % 6) + Math.PI / 6
    ring.push([lng + dLng * Math.cos(angle), lat + dLat * Math.sin(angle)])
  }
  return ring
}

/** Height in meters of a column for a lead score (0..100); never flat so cold leads still show. */
export function columnHeight(score: number | null | undefined, scale = 1) {
  const value = Math.max(0, Math.min(100, Number(score ?? 40) || 0))
  return (60 + value * 9) * scale
}

/** [[west, south], [east, north]] of the points, or null when there are none. */
export function bounds(points: LngLat[]): [LngLat, LngLat] | null {
  if (!points.length) return null
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity
  for (const [lng, lat] of points) {
    west = Math.min(west, lng); east = Math.max(east, lng)
    south = Math.min(south, lat); north = Math.max(north, lat)
  }
  return [[west, south], [east, north]]
}
