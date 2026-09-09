import assert from "node:assert/strict"
import { test } from "node:test"
import { parseHunterJob, parseHunterHistory, requestHunter } from "../src/lib/api/hunter-client.ts"

const job = { id: "saved-search", market: "b2b", query: "clínicas", location: "SP", sources: ["web"], result_limit: 10, status: "completed", results: [{ id: "lead-1", source: "web", title: "Clínica", url: "https://example.com", summary: "Informação pública" }] }

test("accepts completed results and a genuine empty history", () => {
  assert.equal(parseHunterJob(job).results.length, 1)
  assert.deepEqual(parseHunterHistory({ items: [] }), [])
})
test("does not silently treat missing or malformed payloads as no results", () => {
  for (const invalid of [{}, null, { items: {} }, { items: [{}] }]) assert.throws(() => parseHunterHistory(invalid))
  assert.throws(() => parseHunterJob({ ...job, results: null }))
  assert.throws(() => parseHunterJob({ ...job, status: "unknown" }))
})
test("rejects unsafe links from external results", () => {
  assert.throws(() => parseHunterJob({ ...job, results: [{ ...job.results[0], url: "javascript:alert(1)" }] }))
})
test("HTML 200 is an explicit failure, not an empty success", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("<html>Login</html>", { status: 200 }))
  await assert.rejects(requestHunter("/test"), /não retornou os dados/)
})
test("expired sessions have an actionable message", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({}, { status: 401 }))
  await assert.rejects(requestHunter("/test"), /sessão expirou/)
})
test("a network request is bounded and advises recovering saved results", async (t) => {
  t.mock.method(globalThis, "fetch", (_, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")))
  }))
  await assert.rejects(requestHunter("/test", {}, 15), /Atualizar resultados antes de repetir/)
})
