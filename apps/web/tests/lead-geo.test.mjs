import assert from "node:assert/strict"
import { test } from "node:test"
import { bounds, columnHeight, coordinatesFromMapsUrl, hexagon } from "../src/lib/lead-geo.ts"

test("reads the business pin from a Google Maps place link", () => {
  const url = "https://www.google.com/maps/place/Pet+Fort/data=!4m7!3m6!1s0x95197:0x1!8m2!3d-29.9177!4d-51.1834!16s%2Fg%2F11"
  assert.deepEqual(coordinatesFromMapsUrl(url), [-51.1834, -29.9177])
})

test("prefers the pin over the camera and falls back to the camera", () => {
  assert.deepEqual(coordinatesFromMapsUrl("https://www.google.com/maps/place/X/@-30.0,-51.0,15z/data=!3d-29.5!4d-50.5"), [-50.5, -29.5])
  assert.deepEqual(coordinatesFromMapsUrl("https://www.google.com/maps/search/dentista/@-30.0346,-51.2177,13z"), [-51.2177, -30.0346])
})

test("ignores links without usable coordinates", () => {
  for (const url of [null, "", "https://exemplo.com.br", "https://www.google.com/maps/@0.0,0.0,3z", "https://www.google.com/maps/@95.1,10.2,3z"]) {
    assert.equal(coordinatesFromMapsUrl(url), null, String(url))
  }
})

test("column geometry is closed and grows with the score", () => {
  const ring = hexagon([-51.2, -30], 40)
  assert.equal(ring.length, 7)
  assert.deepEqual(ring[0], ring[6])
  assert.ok(columnHeight(90) > columnHeight(40))
  assert.ok(columnHeight(0) > 0)
  assert.deepEqual(bounds([[-51, -30], [-50, -29]]), [[-51, -30], [-50, -29]])
  assert.equal(bounds([]), null)
})

test("the served MapLibre worker matches the installed library version", async () => {
  const { readFile } = await import("node:fs/promises")
  const installed = JSON.parse(await readFile(new URL("../node_modules/maplibre-gl/package.json", import.meta.url), "utf8")).version
  const served = await readFile(new URL("../public/vendor/maplibre-gl-worker.mjs", import.meta.url), "utf8")
  assert.ok(served.slice(0, 400).includes(`v${installed}/LICENSE`), "copy node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs to public/vendor/")
})
